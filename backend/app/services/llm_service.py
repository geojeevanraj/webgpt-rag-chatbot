import asyncio
import logging
import time
from typing import Any
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
import aiohttp
from app.core.config import settings

logger = logging.getLogger(__name__)


# --- Normalised Exceptions ---

class LLMException(Exception):
    """Base exception for LLM service errors."""
    pass


class RateLimitExceeded(LLMException):
    """Raised when an LLM provider returns a rate limit or quota exhausted error."""
    pass


class AIServiceUnavailable(LLMException):
    """Raised when an LLM provider is overloaded or network is down."""
    pass


# --- Provider Interfaces ---

class BaseLLMProvider:
    """Interface that all LLM providers must implement."""

    async def generate_answer(self, system_prompt: str, context: str, question: str) -> str:
        raise NotImplementedError("Providers must implement generate_answer")


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

        except Exception as e:
            err_msg = str(e).lower()
            if "429" in err_msg or "quota" in err_msg or "resource_exhausted" in err_msg or "exhausted" in err_msg:
                raise RateLimitExceeded(f"Gemini Rate Limit: {e}") from e
            elif "503" in err_msg or "overloaded" in err_msg or "unavailable" in err_msg:
                raise AIServiceUnavailable(f"Gemini Service Temporarily Busy: {e}") from e
            else:
                raise LLMException(f"Gemini generation failed: {e}") from e




# --- Orchestration Service Layer ---

async def generate_with_retry(
    provider_name: str,
    model_name: str,
    api_key: str,
    system_prompt: str,
    context: str,
    question: str
) -> str:
    """Invoke the provider's generate_answer method with exponential backoff retries."""
    if provider_name == "gemini":
        provider = GeminiProvider(model_name, api_key)
    else:
        raise LLMException(f"Unsupported provider: {provider_name}")

    backoff = settings.RETRY_BACKOFF_SECONDS
    
    for attempt in range(1, settings.MAX_RETRIES + 1):
        start_time = time.time()
        try:
            logger.info(
                "[LLM] Provider: %s | Model: %s | Attempt: %d | Status: Pending",
                provider_name.capitalize(), model_name, attempt
            )
            answer = await provider.generate_answer(system_prompt, context, question)
            elapsed = time.time() - start_time
            logger.info(
                "[LLM] Provider: %s | Model: %s | Attempt: %d | Status: Success | Latency: %.2f seconds",
                provider_name.capitalize(), model_name, attempt, elapsed
            )
            return answer
        except (RateLimitExceeded, AIServiceUnavailable) as err:
            logger.warning(
                "[LLM] Provider: %s | Model: %s | Attempt: %d | Status: Failed | Reason: %s",
                provider_name.capitalize(), model_name, attempt, err
            )
            if attempt < settings.MAX_RETRIES:
                wait_time = backoff * (2 ** (attempt - 1))
                logger.info("Retrying in %.1f seconds...", wait_time)
                await asyncio.sleep(wait_time)
            else:
                raise
        except Exception as err:
            # Fail fast on bad requests, invalid key formats, prompt blocks
            logger.error(
                "[LLM] Provider: %s | Model: %s | Attempt: %d | Status: Fast-Fail | Reason: %s",
                provider_name.capitalize(), model_name, attempt, err
            )
            raise


async def generate_llm_answer(context: str, question: str) -> str:
    """Orchestrate answer generation across fallback models.

    Deterministic fallback order:
    1. Primary Gemini Model (Gemini 2.5 Flash)
    2. Fallback Gemini Model 1 (Gemini 2.5 Flash Lite)
    3. Fallback Gemini Model 2 (Gemini 1.5 Flash)
    """
    system_prompt = (
        "You are WebGPT.\n"
        "Answer ONLY using the retrieved context.\n"
        "Never invent information.\n"
        "If the answer cannot be found in the retrieved context, explicitly state that "
        "\"I don't have enough information from the scraped content to answer this question.\".\n"
        "Answer naturally without including any inline citation markers (such as [Source 1], [1], (Source 2), or Source 3) in the response text. Do not cite source numbers or labels anywhere in the response body."
    )

    models_sequence = [
        # (provider, model_name, api_key)
        (settings.PRIMARY_PROVIDER, settings.PRIMARY_MODEL, settings.GEMINI_API_KEY),
        ("gemini", settings.FALLBACK_MODEL_1, settings.GEMINI_API_KEY),
        ("gemini", settings.FALLBACK_MODEL_2, settings.GEMINI_API_KEY),
    ]

    last_error = None
    for provider, model_name, api_key in models_sequence:
        if not api_key:
            logger.warning("[LLM] Skipping %s/%s: API key is not configured.", provider, model_name)
            continue

        try:
            answer = await generate_with_retry(
                provider, model_name, api_key, system_prompt, context, question
            )
            return answer
        except Exception as e:
            logger.warning(
                "[LLM] Provider %s model %s failed after maximum attempts. Falling back to next options. Error: %s",
                provider, model_name, e
            )
            last_error = e

    if last_error:
        # Check if the last error is a rate limit or service busy error and raise appropriate normalized error
        err_msg = str(last_error).lower()
        if "rate limit" in err_msg or "quota" in err_msg or "busy" in err_msg:
            raise RateLimitExceeded("The AI service is temporarily busy. Please try again in a moment.")
        raise AIServiceUnavailable(f"AI generation failed: {last_error}")
    else:
        raise AIServiceUnavailable("No LLM providers were configured with valid API keys.")
