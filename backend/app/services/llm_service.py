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


# ---------------------------------------------------------------------------
# Streaming Generation
# ---------------------------------------------------------------------------

# Buffer configuration for streaming deltas
_STREAM_BUFFER_TIMEOUT_MS = 20   # Max ms to wait before flushing buffer
_STREAM_BUFFER_MAX_CHARS = 80    # Max chars before forced flush


async def generate_answer_stream(
    context: str,
    question: str,
):
    """Async generator that streams text deltas from Gemini.

    Yields tuples of ``(event_type, data)`` where event_type is one of:
    - ``"start"``   -> ``{"model": str}``
    - ``"delta"``   -> ``{"text": str}``
    - ``"metrics"`` -> ``{"ttft_ms": float, "generation_ms": float, ...}``

    Model fallback is permitted **only before the first chunk** is emitted.
    Once streaming begins, the active model is locked until completion.

    Small Gemini fragments are buffered for up to 20ms / 80 chars before
    yielding to reduce SSE overhead.
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
    api_key = settings.GEMINI_API_KEY

    available = [m for m in model_chain if not _is_on_cooldown(m)]
    if not available:
        logger.warning("[LLM-Stream] All models on cooldown. Attempting all as last resort.")
        available = list(model_chain)

    last_error: Exception | None = None

    for model_name in available:
        try:
            async for item in _try_model_stream(
                model_name, api_key, system_prompt, context, question,
            ):
                yield item
            # If we get here, streaming completed successfully
            return
        except _StreamPreStartError as err:
            # Failed before first chunk — eligible for fallback
            logger.warning(
                "[LLM-Stream] Model '%s' failed before first chunk: %s", model_name, err,
            )
            _place_on_cooldown(model_name)
            last_error = err
            continue
        except Exception as err:
            # Failed after streaming started — cannot fallback
            logger.error(
                "[LLM-Stream] Model '%s' failed during streaming: %s", model_name, err,
            )
            raise

    raise AIServiceUnavailable(
        "All configured AI models are temporarily unavailable. Please try again shortly."
    )


class _StreamPreStartError(LLMException):
    """Raised when streaming fails before any content is emitted."""
    pass


async def _try_model_stream(
    model_name: str,
    api_key: str,
    system_prompt: str,
    context: str,
    question: str,
):
    """Stream from a single Gemini model with buffering and metrics.

    Yields ``("start", ...)``, ``("delta", ...)``, ``("metrics", ...)`` tuples.
    Raises ``_StreamPreStartError`` if failure occurs before first chunk.
    """
    prompt = (
        f"SYSTEM INSTRUCTIONS:\n{system_prompt}\n\n"
        f"--- CONTEXT ---\n{context}\n--- END CONTEXT ---\n\n"
        f"USER QUESTION:\n{question}"
    )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    config = GenerationConfig(
        temperature=0.3,
        max_output_tokens=2048,
        top_p=0.95,
    )

    gen_start = time.time()
    first_chunk_emitted = False
    ttft_ms = 0.0
    total_chars = 0
    buffer = ""

    try:
        # Use the synchronous streaming API in an executor to avoid blocking
        loop = asyncio.get_running_loop()

        # We cannot use async streaming with the current SDK version easily,
        # so we wrap the synchronous stream in a queue-based async pattern.
        chunk_queue: asyncio.Queue = asyncio.Queue()
        sentinel = object()

        def _run_sync_stream():
            try:
                response = model.generate_content(
                    prompt,
                    generation_config=config,
                    stream=True,
                )
                for chunk in response:
                    if chunk.text:
                        chunk_queue.put_nowait(chunk.text)
            except Exception as e:
                chunk_queue.put_nowait(e)
            finally:
                chunk_queue.put_nowait(sentinel)

        # Start the synchronous stream in a thread
        stream_task = loop.run_in_executor(None, _run_sync_stream)

        while True:
            try:
                item = await asyncio.wait_for(
                    chunk_queue.get(),
                    timeout=30.0,  # 30s max wait per chunk
                )
            except asyncio.TimeoutError:
                if not first_chunk_emitted:
                    raise _StreamPreStartError("Timeout waiting for first chunk from Gemini")
                break

            if item is sentinel:
                break

            if isinstance(item, Exception):
                err_msg = str(item).lower()
                if not first_chunk_emitted:
                    if any(p in err_msg for p in _TRANSIENT_PATTERNS):
                        raise _StreamPreStartError(str(item))
                    raise _StreamPreStartError(str(item))
                raise LLMException(f"Gemini stream error: {item}")

            # Accumulate text into buffer
            buffer += item

            # Flush conditions: buffer large enough or timeout
            if len(buffer) >= _STREAM_BUFFER_MAX_CHARS:
                if not first_chunk_emitted:
                    ttft_ms = (time.time() - gen_start) * 1000
                    yield ("start", {"model": model_name})
                    first_chunk_emitted = True

                total_chars += len(buffer)
                yield ("delta", {"text": buffer})
                buffer = ""
            else:
                # Wait briefly for more chunks to accumulate
                await asyncio.sleep(_STREAM_BUFFER_TIMEOUT_MS / 1000)
                # After short wait, if buffer is non-empty, flush it
                if buffer:
                    if not first_chunk_emitted:
                        ttft_ms = (time.time() - gen_start) * 1000
                        yield ("start", {"model": model_name})
                        first_chunk_emitted = True

                    total_chars += len(buffer)
                    yield ("delta", {"text": buffer})
                    buffer = ""

        # Flush any remaining buffer
        if buffer:
            if not first_chunk_emitted:
                ttft_ms = (time.time() - gen_start) * 1000
                yield ("start", {"model": model_name})
                first_chunk_emitted = True

            total_chars += len(buffer)
            yield ("delta", {"text": buffer})

        # Ensure the executor thread completes
        await stream_task

        if not first_chunk_emitted:
            raise _StreamPreStartError("Gemini returned empty streaming response")

        # Yield metrics
        gen_ms = (time.time() - gen_start) * 1000
        approx_tokens = total_chars // 4  # Rough estimate
        tokens_per_sec = (approx_tokens / (gen_ms / 1000)) if gen_ms > 0 else 0

        yield ("metrics", {
            "ttft_ms": round(ttft_ms, 1),
            "generation_ms": round(gen_ms, 1),
            "characters_streamed": total_chars,
            "tokens_streamed": approx_tokens,
            "tokens_per_second": round(tokens_per_sec, 1),
        })

    except _StreamPreStartError:
        raise
    except (asyncio.TimeoutError, ConnectionError, OSError) as e:
        if not first_chunk_emitted:
            raise _StreamPreStartError(f"Network error: {e}") from e
        raise LLMException(f"Gemini stream network error: {e}") from e
    except Exception as e:
        if not first_chunk_emitted:
            err_msg = str(e).lower()
            if any(p in err_msg for p in _TRANSIENT_PATTERNS):
                raise _StreamPreStartError(str(e)) from e
            raise _StreamPreStartError(str(e)) from e
        raise LLMException(f"Gemini stream error: {e}") from e
