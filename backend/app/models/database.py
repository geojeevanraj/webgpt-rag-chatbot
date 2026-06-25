"""SQLAlchemy ORM models for WebGPT.

Defines three tables:
- ``scrape_jobs``  — tracks URL ingestion jobs and their lifecycle.
- ``scraped_pages`` — records each individual page processed within a job.
- ``chat_messages`` — persists user/assistant conversation history.

All models use UUID primary keys (stored as TEXT in SQLite) and ISO 8601
datetime strings for timestamp columns.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def _generate_uuid() -> str:
    """Generate a new UUID v4 as a string."""
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class ScrapeJob(Base):
    """A URL ingestion job initiated by the user.

    Lifecycle: pending → scraping → completed | failed.
    One job produces one ChromaDB collection (named ``job_{id}``).
    """

    __tablename__ = "scrape_jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_generate_uuid
    )
    seed_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    max_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    max_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    pages_scraped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    pages: Mapped[list["ScrapedPage"]] = relationship(
        "ScrapedPage",
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


    def __repr__(self) -> str:
        return (
            f"<ScrapeJob id={self.id!r} domain={self.domain!r} "
            f"status={self.status!r} pages={self.pages_scraped}>"
        )


class ScrapedPage(Base):
    """An individual page processed during a scrape job.

    Each page may produce zero or more text chunks stored in ChromaDB.
    A page with status ``failed`` has an ``error_message`` explaining why.
    """

    __tablename__ = "scraped_pages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_generate_uuid
    )
    job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("scrape_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    depth: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # Relationship back to parent job
    job: Mapped["ScrapeJob"] = relationship("ScrapeJob", back_populates="pages")

    def __repr__(self) -> str:
        return (
            f"<ScrapedPage id={self.id!r} url={self.url!r} "
            f"status={self.status!r} chunks={self.chunk_count}>"
        )


class ChatMessage(Base):
    """A single message in a conversation.

    Messages are scoped to a specific scrape job via ``job_id``. A NULL
    ``job_id`` indicates a global chat (searching all sources).

    For assistant messages, the ``sources`` column stores a JSON-serialized
    list of ``SourceCitation`` objects used to generate the answer.
    """

    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_generate_uuid
    )
    job_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("scrape_jobs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # Relationship back to parent job (nullable)
    job: Mapped["ScrapeJob | None"] = relationship(
        "ScrapeJob", back_populates="messages"
    )

    def __repr__(self) -> str:
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<ChatMessage id={self.id!r} role={self.role!r} content={content_preview!r}>"



