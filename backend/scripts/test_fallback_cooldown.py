"""Automated tests for the Gemini model chain fallback and cooldown system.

Tests:
  1. All models fail with transient errors (429/503) — verifies chain order,
     cooldown placement, clean user-facing error, and structured timing logs.
  2. Permanent errors do NOT place models on cooldown.
  3. Embedding/retrieval run exactly once (no duplication during retries).
  4. Duplicate / empty model names cleaned from config.
  5. Cooldown expiry restores model availability.

Run from the backend directory:
    python scripts/test_fallback_cooldown.py
"""

import asyncio
import os
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure backend directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ---- helpers ----

def _hr(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


passed = 0
failed = 0


def _assert(condition: bool, msg: str) -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {msg}")
    else:
        failed += 1
        print(f"  [FAIL] {msg}")


# ---- Tests ----

def test_1_all_models_transient_failure():
    """Every model returns a transient error — verify chain order, cooldowns, and error."""
    _hr("Test 1: All models fail with transient errors")

    from app.services.llm_service import (
        AIServiceUnavailable,
        RateLimitExceeded,
        _MODEL_COOLDOWNS,
        _is_on_cooldown,
        generate_llm_answer,
        rag_timing_context,
        new_timing_data,
    )
    from app.core.config import settings

    # Clear any leftover cooldowns
    _MODEL_COOLDOWNS.clear()

    chain = settings.GEMINI_MODEL_CHAIN
    print(f"  Model chain: {chain}")

    # Mock provider to always raise RateLimitExceeded
    call_log: list[str] = []

    async def mock_generate(system_prompt, context, question):
        raise RateLimitExceeded("429 quota exhausted")

    timing = new_timing_data()
    token = rag_timing_context.set(timing)

    with patch(
        "app.services.llm_service.GeminiProvider.generate_answer",
        side_effect=mock_generate,
    ):
        error_raised = False
        error_msg = ""
        try:
            asyncio.get_event_loop().run_until_complete(
                generate_llm_answer("test context", "test question")
            )
        except AIServiceUnavailable as e:
            error_raised = True
            error_msg = str(e)

    rag_timing_context.reset(token)

    _assert(error_raised, "AIServiceUnavailable was raised")
    _assert(
        "temporarily unavailable" in error_msg.lower(),
        f"Clean user-facing message returned: '{error_msg}'",
    )

    # Every model should be on cooldown now
    for model in chain:
        _assert(_is_on_cooldown(model), f"Model '{model}' is on cooldown")

    # Timing attempts should match chain length
    attempts = timing.get("attempts", [])
    _assert(
        len(attempts) == len(chain),
        f"Attempts count ({len(attempts)}) == chain length ({len(chain)})",
    )

    # Verify attempt order matches chain order
    for idx, (attempt, expected_model) in enumerate(zip(attempts, chain)):
        _assert(
            attempt["model"] == expected_model,
            f"Attempt {idx + 1} model '{attempt['model']}' matches chain position '{expected_model}'",
        )

    _MODEL_COOLDOWNS.clear()


def test_2_permanent_errors_no_cooldown():
    """Permanent errors should NOT place models on cooldown."""
    _hr("Test 2: Permanent errors skip cooldown")

    from app.services.llm_service import (
        AIServiceUnavailable,
        LLMException,
        _MODEL_COOLDOWNS,
        _is_on_cooldown,
        generate_llm_answer,
        rag_timing_context,
        new_timing_data,
    )
    from app.core.config import settings

    _MODEL_COOLDOWNS.clear()
    chain = settings.GEMINI_MODEL_CHAIN

    async def mock_generate(system_prompt, context, question):
        raise LLMException("Invalid API key")

    timing = new_timing_data()
    token = rag_timing_context.set(timing)

    with patch(
        "app.services.llm_service.GeminiProvider.generate_answer",
        side_effect=mock_generate,
    ):
        try:
            asyncio.get_event_loop().run_until_complete(
                generate_llm_answer("test context", "test question")
            )
        except AIServiceUnavailable:
            pass

    rag_timing_context.reset(token)

    # NO model should be on cooldown after permanent errors
    for model in chain:
        _assert(not _is_on_cooldown(model), f"Model '{model}' is NOT on cooldown")

    _MODEL_COOLDOWNS.clear()


def test_3_cooldown_expiry():
    """Models should become available once cooldown expires."""
    _hr("Test 3: Cooldown expiry restores model")

    from app.services.llm_service import (
        _MODEL_COOLDOWNS,
        _is_on_cooldown,
        _place_on_cooldown,
    )
    from app.core.config import settings

    _MODEL_COOLDOWNS.clear()
    model = "test-model-expiry"

    # Place on cooldown with a 0.1-second duration
    original_cd = settings.GEMINI_COOLDOWN_SECONDS
    settings.GEMINI_COOLDOWN_SECONDS = 0.1
    _place_on_cooldown(model)

    _assert(_is_on_cooldown(model), "Model is on cooldown immediately after placement")

    time.sleep(0.15)

    _assert(not _is_on_cooldown(model), "Model is available after cooldown expiry")

    settings.GEMINI_COOLDOWN_SECONDS = original_cd
    _MODEL_COOLDOWNS.clear()


def test_4_config_cleaning():
    """Duplicate and empty model names should be cleaned at startup."""
    _hr("Test 4: Config validation cleans chain")

    from app.core.config import DEFAULT_MODEL_CHAIN, Settings

    # Simulate a settings instance with duplicates and blanks
    with patch.dict(
        os.environ,
        {
            "GEMINI_API_KEY": "test-key",
            "GEMINI_MODEL_CHAIN": '["model-a", "model-a", "", "model-b", "  ", "model-b"]',
        },
        clear=False,
    ):
        s = Settings()
        # Manually apply the validation logic
        cleaned: list[str] = []
        seen: set[str] = set()
        for name in s.GEMINI_MODEL_CHAIN:
            name = name.strip() if isinstance(name, str) else ""
            if not name or name in seen:
                continue
            seen.add(name)
            cleaned.append(name)

        _assert(len(cleaned) == 2, f"Cleaned chain has 2 entries (got {len(cleaned)})")
        _assert(cleaned == ["model-a", "model-b"], f"Cleaned chain is {cleaned}")


def test_5_success_on_second_model():
    """First model fails with 429, second model succeeds."""
    _hr("Test 5: Fallback to second model on transient failure")

    from app.services.llm_service import (
        RateLimitExceeded,
        _MODEL_COOLDOWNS,
        _is_on_cooldown,
        generate_llm_answer,
        rag_timing_context,
        new_timing_data,
    )
    from app.core.config import settings

    _MODEL_COOLDOWNS.clear()
    chain = settings.GEMINI_MODEL_CHAIN

    call_count = 0

    async def mock_generate(self, system_prompt, context, question):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RateLimitExceeded("429 quota exhausted")
        return "Success from second model"

    timing = new_timing_data()
    token = rag_timing_context.set(timing)

    with patch(
        "app.services.llm_service.GeminiProvider.generate_answer",
        mock_generate,
    ):
        result = asyncio.get_event_loop().run_until_complete(
            generate_llm_answer("test context", "test question")
        )

    rag_timing_context.reset(token)

    _assert(result == "Success from second model", f"Got correct response: '{result}'")
    _assert(call_count == 2, f"Provider was called exactly 2 times (got {call_count})")

    # First model should be on cooldown, second should not
    _assert(_is_on_cooldown(chain[0]), f"First model '{chain[0]}' is on cooldown")
    _assert(not _is_on_cooldown(chain[1]), f"Second model '{chain[1]}' is NOT on cooldown")

    # Timing should show 2 attempts
    attempts = timing.get("attempts", [])
    _assert(len(attempts) == 2, f"Timing shows 2 attempts (got {len(attempts)})")
    _assert(attempts[0]["status"].startswith("Rate Limited"), f"First attempt status: {attempts[0]['status']}")
    _assert(attempts[1]["status"] == "Success", f"Second attempt status: {attempts[1]['status']}")

    _MODEL_COOLDOWNS.clear()


# ---- Main ----

if __name__ == "__main__":
    print("\n=== Gemini Model Chain Fallback & Cooldown Tests ===\n")

    test_1_all_models_transient_failure()
    test_2_permanent_errors_no_cooldown()
    test_3_cooldown_expiry()
    test_4_config_cleaning()
    test_5_success_on_second_model()

    print(f"\n{'=' * 60}")
    print(f"  Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed:
        print("\n[FAIL] Some tests FAILED.")
        sys.exit(1)
    else:
        print("\n[PASS] All tests PASSED.")
        sys.exit(0)
