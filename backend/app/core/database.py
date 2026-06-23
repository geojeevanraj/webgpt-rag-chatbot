"""Async SQLite database engine, session factory, and dependency injection.

Provides:
- An async SQLAlchemy engine backed by aiosqlite.
- An async session factory for creating scoped database sessions.
- A FastAPI dependency (``get_db``) that yields a session per request.
- An ``init_db`` coroutine to create all tables on application startup.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

logger = logging.getLogger(__name__)

# --- Engine ---
# SQLite-specific: check_same_thread=False is required for async usage.
# pool_pre_ping=True verifies connections before handing them out.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
    """Enable WAL journal mode and foreign key enforcement on every new SQLite connection.

    WAL (Write-Ahead Logging) allows concurrent readers while a write is in progress,
    which is critical for a web server that reads scrape status while background tasks
    write scrape progress.

    Foreign keys are off by default in SQLite — we need them for CASCADE deletes.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


# --- Session Factory ---
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides a scoped async database session.

    Usage in a route::

        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...

    The session is committed on success and rolled back on any unhandled exception.
    It is always closed when the request finishes.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all ORM tables if they don't exist.

    Called once during application startup via the FastAPI lifespan handler.
    Imports the ORM models to ensure they are registered with the Base metadata
    before ``create_all`` is invoked.
    """
    # Import models so SQLAlchemy registers them with Base.metadata.
    import app.models.database as _models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(_models.Base.metadata.create_all)

    logger.info("Database tables created successfully.")
