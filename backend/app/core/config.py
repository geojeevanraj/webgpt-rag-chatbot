"""Application configuration via environment variables.

Uses Pydantic BaseSettings to load and validate configuration from a .env file
and environment variables. All settings have sensible defaults.
"""

import json
import logging
import os
import sys
from typing import Any
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Default model chain — used when the configured chain is empty or malformed.
# Order reflects quality-first priority, progressively falling back to lighter models.
DEFAULT_MODEL_CHAIN: list[str] = [
    "gemini-2.5-flash",
    "gemini-3.5-flash",
    "gemini-3-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
]


class Settings(BaseSettings):
    """Central configuration for the WebGPT application.

    Loads values from environment variables and a .env file (env file takes
    lower precedence than actual environment variables). Validates types and
    constraints at startup — a misconfigured deployment fails fast.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Required (Defaults to empty string to allow defensive startup checks to run) ---
    GEMINI_API_KEY: str = ""

    # --- Database ---
    DATABASE_URL: str = "sqlite+aiosqlite:///./webgpt.db"

    # --- ChromaDB ---
    CHROMA_PERSIST_DIR: str = "./chroma_data"

    # --- Models & Multi-LLM provider config ---
    EMBEDDING_MODEL: str = "models/gemini-embedding-001"
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Configurable model fallback chain (native JSON array in .env).
    # Order is the single source of truth for priority.
    GEMINI_MODEL_CHAIN: list[str] = DEFAULT_MODEL_CHAIN.copy()

    # Cooldown duration (seconds) for models that fail with transient errors.
    GEMINI_COOLDOWN_SECONDS: float = 60.0

    MAX_RETRIES: int = 3
    RETRY_BACKOFF_SECONDS: float = 2.0

    # --- Chunking ---
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # --- Retrieval ---
    MAX_RETRIEVAL_RESULTS: int = 5
    RELEVANCE_THRESHOLD: float = 1.2

    # --- Scraping ---
    SCRAPE_DELAY_SECONDS: float = 1.0
    SCRAPE_TIMEOUT_SECONDS: int = 20
    SCRAPE_MAX_DEPTH: int = 2
    SCRAPE_MAX_PAGES: int = 50

    # --- Browser Rendering Fallback ---
    BROWSER_RENDER_ENABLED: bool = True
    BROWSER_RENDER_TIMEOUT: int = 30
    MIN_CONTENT_LENGTH: int = 100

    # --- CORS (String-based configuration to prevent fragile Pydantic JSON decoding errors) ---
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:3000"


    @field_validator("GEMINI_MODEL_CHAIN", mode="before")
    @classmethod
    def parse_model_chain(cls, v: Any) -> list[str]:
        """Parse GEMINI_MODEL_CHAIN from env.

        Accepts a native JSON array string (e.g. '["model-a","model-b"]').
        Falls back to the default chain on any parsing failure.
        """
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return DEFAULT_MODEL_CHAIN.copy()
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
            # If it's not valid JSON, fall back to defaults
            logger.warning(
                "GEMINI_MODEL_CHAIN value is not a valid JSON array: '%s'. "
                "Using default model chain.",
                v,
            )
            return DEFAULT_MODEL_CHAIN.copy()
        return DEFAULT_MODEL_CHAIN.copy()


# Module-level singleton — imported by other modules as `from app.core.config import settings`.
settings = Settings()


def validate_startup() -> None:
    """Execute defensive validation checks on startup settings.

    Ensures that missing API keys, unwritable database/vector paths, invalid
    CORS configuration strings, and malformed model chains are caught at launch
    with clear errors printed to stderr.
    """
    errors = []

    # 1. Validate GEMINI_API_KEY
    api_key = settings.GEMINI_API_KEY.strip()
    if not api_key:
        errors.append("GEMINI_API_KEY environment variable is missing or empty.")
    elif api_key in ("your_gemini_api_key_here", "test_key_for_phase1_verification"):
        errors.append(f"GEMINI_API_KEY contains a placeholder value: '{api_key}'")

    # 2. Validate database path config
    db_url = settings.DATABASE_URL.strip()
    if not db_url:
        errors.append("DATABASE_URL environment variable is missing or empty.")
    elif db_url.startswith("sqlite+aiosqlite:///"):
        db_path = db_url.replace("sqlite+aiosqlite:///", "")
        # Get directory path of the SQLite database
        db_dir = os.path.dirname(db_path)
        # If relative path without explicit directory (e.g. 'webgpt.db'), it uses current directory
        if not db_dir:
            db_dir = "."
        
        # If directory doesn't exist, attempt to create it.
        if not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except Exception as e:
                errors.append(f"DATABASE_URL directory '{db_dir}' does not exist and cannot be created: {e}")
        elif not os.access(db_dir, os.W_OK):
            errors.append(f"DATABASE_URL directory '{db_dir}' is not writable.")

    # 3. Validate ChromaDB path
    chroma_dir = settings.CHROMA_PERSIST_DIR.strip()
    if not chroma_dir:
        errors.append("CHROMA_PERSIST_DIR environment variable is missing or empty.")
    else:
        if not os.path.exists(chroma_dir):
            try:
                os.makedirs(chroma_dir, exist_ok=True)
            except Exception as e:
                errors.append(f"CHROMA_PERSIST_DIR directory '{chroma_dir}' does not exist and cannot be created: {e}")
        elif not os.access(chroma_dir, os.W_OK):
            errors.append(f"CHROMA_PERSIST_DIR directory '{chroma_dir}' is not writable.")

    # 4. Parse and Validate CORS Origins formats
    cors_raw = settings.CORS_ORIGINS.strip()
    cors_origins = []
    if cors_raw:
        if cors_raw.startswith("[") and cors_raw.endswith("]"):
            try:
                parsed = json.loads(cors_raw)
                if isinstance(parsed, list):
                    cors_origins = [str(item).strip() for item in parsed]
            except Exception:
                pass
        if not cors_origins:
            cors_origins = [item.strip() for item in cors_raw.split(",") if item.strip()]

    if not cors_origins:
        errors.append("CORS_ORIGINS parsed list is empty.")
    else:
        for origin in cors_origins:
            if origin == "*":
                continue
            parsed = urlparse(origin)
            if not parsed.scheme or parsed.scheme not in ("http", "https") or not parsed.netloc:
                errors.append(
                    f"CORS_ORIGINS contains an invalid origin URL: '{origin}'. "
                    "Origins must use http/https scheme and specify a host (e.g., https://example.com)."
                )

    # 5. Validate and clean GEMINI_MODEL_CHAIN
    raw_chain = settings.GEMINI_MODEL_CHAIN
    cleaned: list[str] = []
    seen: set[str] = set()
    for model_name in raw_chain:
        name = model_name.strip() if isinstance(model_name, str) else ""
        if not name:
            continue
        if name in seen:
            logger.warning("Duplicate model '%s' removed from GEMINI_MODEL_CHAIN.", name)
            continue
        seen.add(name)
        cleaned.append(name)

    if not cleaned:
        logger.warning(
            "GEMINI_MODEL_CHAIN is empty after validation. Falling back to default chain."
        )
        cleaned = DEFAULT_MODEL_CHAIN.copy()

    # Apply the cleaned chain back to settings (Pydantic v2 allows mutation)
    settings.GEMINI_MODEL_CHAIN = cleaned
    logger.info("Final validated GEMINI_MODEL_CHAIN: %s", cleaned)

    if errors:
        print("\n" + "=" * 80, file=sys.stderr)
        print("CRITICAL CONFIGURATION ERROR: Backend application startup failed.", file=sys.stderr)
        print("Please resolve the following configuration issues before launching:", file=sys.stderr)
        for idx, err in enumerate(errors, 1):
            print(f"  {idx}. {err}", file=sys.stderr)
        print("=" * 80 + "\n", file=sys.stderr)
        sys.exit(1)


# Execute startup validations immediately on configuration import
validate_startup()
