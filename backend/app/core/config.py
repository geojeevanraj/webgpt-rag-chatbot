"""Application configuration via environment variables.

Uses Pydantic BaseSettings to load and validate configuration from a .env file
and environment variables. All settings have sensible defaults except for
GEMINI_API_KEY which must be provided.
"""

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

    # --- Required ---
    GEMINI_API_KEY: str

    # --- Database ---
    DATABASE_URL: str = "sqlite+aiosqlite:///./webgpt.db"

    # --- ChromaDB ---
    CHROMA_PERSIST_DIR: str = "./chroma_data"

    # --- Models ---
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    GEMINI_MODEL: str = "gemini-2.5-flash"

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

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]


# Module-level singleton — imported by other modules as `from app.core.config import settings`.
# Instantiation validates all settings immediately; missing GEMINI_API_KEY crashes here.
settings = Settings()  # type: ignore[call-arg]
