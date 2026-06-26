"""FastAPI application factory and entrypoint.

Creates the FastAPI app, configures CORS, registers API routers, and
defines the application lifespan (startup/shutdown logic).

Run with::

    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db

# Configure logging for the entire application
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("webgpt")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler — runs startup and shutdown logic.

    Startup:
        1. Creates SQLite database tables if they don't exist.
        2. Logs the configuration summary.

    Shutdown:
        1. Logs a clean shutdown message.

    Note: Embedding model warm-up will be added in Phase 2 when
    the embedder service is implemented.
    """
    # --- Startup ---
    logger.info("Starting WebGPT API...")
    await init_db()
    logger.info("Database initialized.")
    logger.info("Gemini API key loaded: %s", bool(settings.GEMINI_API_KEY.strip()))
    logger.info("Gemini model chain: %s", settings.GEMINI_MODEL_CHAIN)
    logger.info("Gemini cooldown: %.0fs", settings.GEMINI_COOLDOWN_SECONDS)
    logger.info(
        "Configuration: embedding_model=%s, chunk_size=%d, chunk_overlap=%d",
        settings.EMBEDDING_MODEL,
        settings.CHUNK_SIZE,
        settings.CHUNK_OVERLAP,
    )
    logger.info("WebGPT API is ready.")

    yield

    # --- Shutdown ---
    logger.info("WebGPT API shutting down.")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance.

    Returns:
        A fully configured FastAPI app with CORS, routers, and lifespan.
    """
    application = FastAPI(
        title="WebGPT API",
        description=(
            "RAG-powered chatbot that ingests websites via recursive scraping "
            "and answers questions grounded in the collected content."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # --- CORS ---
    # Parse and clean CORS_ORIGINS from settings string to support JSON lists or comma-separated lists
    cors_raw = settings.CORS_ORIGINS.strip()
    cors_origins = []
    if cors_raw:
        if cors_raw.startswith("[") and cors_raw.endswith("]"):
            try:
                import json
                parsed = json.loads(cors_raw)
                if isinstance(parsed, list):
                    cors_origins = [str(item).strip() for item in parsed]
            except Exception:
                pass
        if not cors_origins:
            cors_origins = [item.strip() for item in cors_raw.split(",") if item.strip()]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Health Check ---
    @application.get(
        "/health",
        tags=["Health"],
        summary="Health check endpoint",
    )
    async def health_check() -> dict[str, str]:
        """Returns service health status. Used by monitoring and readiness probes."""
        return {"status": "healthy", "service": "webgpt-api"}

    # --- Routers ---
    # Routers are registered here. Placeholder routes are included in this phase
    # to verify the app boots correctly. Full route implementations come in Phase 2/3.
    _register_routers(application)

    return application


def _register_routers(application: FastAPI) -> None:
    """Register all API routers with the application.

    Separated into its own function to keep ``create_app`` clean and to make
    the import-time cost explicit. Routers that don't exist yet are guarded
    with try/except so Phase 1 boots cleanly without Phase 2/3 code.
    """
    try:
        from app.api.scrape import router as scrape_router

        application.include_router(scrape_router, prefix="/api", tags=["Scraping"])
        logger.info("Registered scrape router.")
    except ImportError:
        logger.warning("Scrape router not found — skipping. (Expected in Phase 1)")

    try:
        from app.api.chat import router as chat_router

        application.include_router(chat_router, prefix="/api", tags=["Chat"])
        logger.info("Registered chat router.")
    except ImportError:
        logger.warning("Chat router not found — skipping. (Expected in Phase 1)")

    try:
        from app.api.sources import router as sources_router

        application.include_router(sources_router, prefix="/api", tags=["Sources"])
        logger.info("Registered sources router.")
    except ImportError:
        logger.warning("Sources router not found — skipping. (Expected in Phase 1)")


# Create the app instance — this is what uvicorn imports.
app = create_app()
