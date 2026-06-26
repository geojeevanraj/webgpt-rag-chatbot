"""LLM Orchestration Service with configurable model chain and cooldown fallback.

Provides a multi-model fallback system that iterates through a configured list
of Gemini models.  Models that fail with transient errors (HTTP 429, 503,
quota/resource exhaustion, network timeouts) are placed on a temporary in-memory
cooldown so subsequent requests skip them automatically.

Permanent errors (invalid key, unknown model, blocked prompts) fail fast without
cooldown.
"""

import asyncio
import contextvars
import logging
import time
import uuid
from typing import Any

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalised Exceptions
# ---------------------------------------------------------------------------

class LLMException(Exception):
    """Base exception for LLM service errors."""
    pass


class RateLimitExceeded(LLMException):
    """Raised when an LLM provider returns a rate limit or quota exhausted error."""
    pass


class AIServiceUnavailable(LLMException):
    """Raised when an LLM provider is overloaded or network is down."""
    pass


# ---------------------------------------------------------------------------
# In-Memory Model Cooldown Tracking
# ---------------------------------------------------------------------------

# Maps model name -> epoch timestamp when cooldown expires.
# Purely in-memory; resets on process restart.
_MODEL_COOLDOWNS: dict[str, float] = {}


def _is_on_cooldown(model_name: str) -> bool:
    """Check whether *model_name* is currently on cooldown."""
    expiry = _MODEL_COOLDOWNS.get(model_name)
    if expiry is None:
        return False
    if time.time() >= expiry:
        # Cooldown expired — clean up entry
        _MODEL_COOLDOWNS.pop(model_name, None)
        return False
    return True


def _place_on_cooldown(model_name: str) -> None:
    """Place *model_name* on cooldown for ``GEMINI_COOLDOWN_SECONDS``."""
    _MODEL_COOLDOWNS[model_name] = time.time() + settings.GEMINI_COOLDOWN_SECONDS
    logger.info(
        "[Cooldown] Model '%s' placed on cooldown for %.0fs.",
        model_name,
        settings.GEMINI_COOLDOWN_SECONDS,
    )


# ---------------------------------------------------------------------------
# RAG Timing Context (per-request)
# ---------------------------------------------------------------------------

rag_timing_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "rag_timing_context"
)


def new_timing_data() -> dict[str, Any]:
    """Create a fresh timing data dictionary for one request."""
    return {
        "request_id": uuid.uuid4().hex[:8],
        "embedding_time": 0.0,
        "retrieval_time": 0.0,
        "prompt_time": 0.0,
        "llm_time": 0.0,
        "total_time": 0.0,
        "attempts": [],  # list[dict] — {"model": str, "status": str, "elapsed": float}
    }


# ---------------------------------------------------------------------------
# Provider Interfaces
# ---------------------------------------------------------------------------

class BaseLLMProvider:
    """Interface that all LLM providers must implement."""

    async def generate_answer(self, system_prompt: str, context: str, question: str) -> str:
        raise NotImplementedError("Providers must implement generate_answer")


# Patterns indicating *transient* failures eligible for cooldown.
_TRANSIENT_PATTERNS = (
    "429", "quota", "resource_exhausted", "exhausted",
    "503", "overloaded", "unavailable",
)


class GeminiProvider(BaseLLMProvider):
    """Provider class for Google Gemini Generative AI API."""

    def __init__(self, model_name: str, api_key: str) -> None:
        self.model_name = model_name
        self.api_key = api_key

    async def generate_answer(self, system_prompt: str, context: str, question: str) -> str:
        prompt = (
            f"SYSTEM INSTRUCTIONS:\n{system_prompt}\n\n"
            f"--- CONTEXT ---\n{context}\n--- END CONTEXT ---\n\n"
            f"USER QUESTION:\n{question}"
        )

        try:
            # Configure the api key for the model client call
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model_name)

            config = GenerationConfig(
                temperature=0.3,
                max_output_tokens=2048,
                top_p=0.95
            )

            # execute CPU/network blocking Google SDK method in a thread pool
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content(prompt, generation_config=config)
            )

            try:
                answer = response.text
                if not answer:
                    raise LLMException("Gemini returned an empty response text.")
                return answer
            except Exception as text_err:
                feedback = getattr(response, "prompt_feedback", "N/A")
                raise LLMException(f"Failed to retrieve text from Gemini. Feedback: {feedback}") from text_err

        except (RateLimitExceeded, AIServiceUnavailable, LLMException):
            # Already normalised — re-raise as-is
            raise
        except (asyncio.TimeoutError, ConnectionError, OSError) as e:
            # Network / connection / timeout errors are transient
            raise AIServiceUnavailable(f"Gemini network error: {e}") from e
        except Exception as e:
            err_msg = str(e).lower()
            # Check for transient failure patterns
            if any(p in err_msg for p in _TRANSIENT_PATTERNS):
                if "429" in err_msg or "quota" in err_msg or "exhausted" in err_msg:
                    raise RateLimitExceeded(f"Gemini Rate Limit: {e}") from e
                raise AIServiceUnavailable(f"Gemini Service Temporarily Busy: {e}") from e
            # Everything else is a permanent / non-retryable error
            raise LLMException(f"Gemini generation failed: {e}") from e


# ---------------------------------------------------------------------------
# Orchestration Service Layer
# ---------------------------------------------------------------------------

async def _try_model(
    model_name: str,
    api_key: str,
    system_prompt: str,
    context: str,
    question: str,
) -> str:
    """Invoke a single Gemini model *without* retries.

    Returns the answer text on success.  Raises on any failure.
    """
    provider = GeminiProvider(model_name, api_key)
    return await provider.generate_answer(system_prompt, context, question)


async def generate_llm_answer(context: str, question: str) -> str:
    """Orchestrate answer generation across the configured model chain.

    Iterates through ``settings.GEMINI_MODEL_CHAIN`` in order, skipping any
    model currently on cooldown.  Transient failures place the model on
    cooldown; permanent failures do not.

    If every model fails, raises ``AIServiceUnavailable`` with a clean
    user-facing message.
    """
    system_prompt = (
        "You are WebGPT.\n"
        "Answer ONLY using the retrieved context.\n"
        "Never invent information.\n"
        "If the answer cannot be found in the retrieved context, explicitly state that "
        "\"I don't have enough information from the scraped content to answer this question.\"\n"
        "Answer naturally without including any inline citation markers (such as [Source 1], [1], (Source 2), or Source 3) in the response text. Do not cite source numbers or labels anywhere in the response body."
    )

    model_chain = settings.GEMINI_MODEL_CHAIN
    total_models = len(model_chain)
    api_key = settings.GEMINI_API_KEY

    # Determine which models are available (not on cooldown).
    available = [m for m in model_chain if not _is_on_cooldown(m)]
    if not available:
        # Every model is on cooldown — try them all anyway as a last resort.
        logger.warning(
            "[LLM] All %d models are on cooldown. Attempting all models as last resort.",
            total_models,
        )
        available = list(model_chain)

    # Retrieve or initialise timing context
    try:
        timing = rag_timing_context.get()
    except LookupError:
        timing = new_timing_data()
        rag_timing_context.set(timing)

    llm_start = time.time()
    last_error: Exception | None = None
    attempt_num = 0

    for model_name in available:
        attempt_num += 1
        chain_pos = model_chain.index(model_name) + 1
        start = time.time()

        logger.info(
            "[LLM] Attempt %d/%d -> %s (chain position %d/%d)",
            attempt_num, len(available), model_name, chain_pos, total_models,
        )

        try:
            answer = await _try_model(
                model_name, api_key, system_prompt, context, question,
            )
            elapsed = time.time() - start
            timing["llm_time"] = time.time() - llm_start
            timing["attempts"].append({
                "model": model_name,
                "status": "Success",
                "elapsed": round(elapsed, 2),
            })
            logger.info(
                "[LLM] Attempt %d/%d -> %s -> Success (%.2fs)",
                attempt_num, len(available), model_name, elapsed,
            )
            return answer

        except (RateLimitExceeded, AIServiceUnavailable) as err:
            # Transient failure — place on cooldown and try next model
            elapsed = time.time() - start
            status = "Rate Limited (429)" if isinstance(err, RateLimitExceeded) else "Service Unavailable (503)"
            timing["attempts"].append({
                "model": model_name,
                "status": status,
                "elapsed": round(elapsed, 2),
            })
            logger.warning(
                "[LLM] Attempt %d/%d -> %s -> %s (%.2fs)",
                attempt_num, len(available), model_name, status, elapsed,
            )
            _place_on_cooldown(model_name)
            last_error = err

        except LLMException as err:
            # Permanent failure — do NOT cooldown, fail fast to next model
            elapsed = time.time() - start
            timing["attempts"].append({
                "model": model_name,
                "status": f"Permanent Error: {err}",
                "elapsed": round(elapsed, 2),
            })
            logger.error(
                "[LLM] Attempt %d/%d -> %s -> Permanent Failure (%.2fs): %s",
                attempt_num, len(available), model_name, elapsed, err,
            )
            last_error = err

    # All models exhausted
    timing["llm_time"] = time.time() - llm_start
    raise AIServiceUnavailable(
        "All configured AI models are temporarily unavailable. Please try again shortly."
    )
