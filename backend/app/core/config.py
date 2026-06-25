"""Application configuration via environment variables.

Uses Pydantic BaseSettings to load and validate configuration from a .env file
and environment variables. All settings have sensible defaults.
"""

import json
import os
import sys
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_API_KEY: str = ""

    PRIMARY_PROVIDER: str = "gemini"
    PRIMARY_MODEL: str = "gemini-2.5-flash"
    FALLBACK_MODEL_1: str = "gemini-2.5-flash-lite"
    FALLBACK_MODEL_2: str = "gemini-1.5-flash"
    FALLBACK_PROVIDER: str = "groq"
    FALLBACK_GROQ_MODEL: str = "llama-3.3-70b-versatile"
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
    SCRAPE_TIMEOUT_SECONDS: int = 10
    SCRAPE_MAX_DEPTH: int = 2
    SCRAPE_MAX_PAGES: int = 50

    # --- CORS (String-based configuration to prevent fragile Pydantic JSON decoding errors) ---
    CORS_ORIGINS: str = "http://localhost:5173"


# Module-level singleton — imported by other modules as `from app.core.config import settings`.
settings = Settings()


def validate_startup() -> None:
    """Execute defensive validation checks on startup settings.

    Ensures that missing API keys, unwritable database/vector paths, and invalid
    CORS configuration strings are caught at launch with clear errors printed to stderr.
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

