"""Pydantic v2 request/response schemas for the WebGPT API.

These schemas serve three purposes:
1. **Validation** — FastAPI uses them to validate incoming request bodies.
2. **Serialization** — FastAPI uses them to serialize outgoing responses.
3. **Documentation** — FastAPI auto-generates OpenAPI docs from these schemas.

Naming convention:
- ``*Request``  — incoming request body.
- ``*Response`` — outgoing response body.
- No suffix     — shared sub-schemas embedded in responses.
"""

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


# =============================================================================
# Scraping Schemas
# =============================================================================


class ScrapeRequest(BaseModel):
    """Request body for ``POST /api/scrape``."""

    url: HttpUrl = Field(
        ...,
        description="The seed URL to scrape. Must be HTTP or HTTPS.",
        examples=["https://docs.python.org/3/tutorial/"],
    )
    max_depth: int = Field(
        default=2,
        ge=1,
        le=3,
        description="Maximum link-following depth from the seed URL.",
    )
    max_pages: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of pages to scrape.",
    )


class ScrapeResponse(BaseModel):
    """Response body for ``POST /api/scrape`` (202 Accepted)."""

    job_id: str
    status: str
    seed_url: str
    created_at: datetime


class PageInfo(BaseModel):
    """Summary of a single scraped page, embedded in status responses."""

    url: str
    title: str
    depth: int
    chunk_count: int
    status: str
    error_message: str | None = None


class ScrapeStatusResponse(BaseModel):
    """Response body for ``GET /api/scrape/{job_id}/status``."""

    job_id: str
    seed_url: str
    domain: str
    status: str
    max_depth: int
    max_pages: int
    pages_scraped: int
    pages_failed: int
    total_chunks: int
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    pages: list[PageInfo] = Field(default_factory=list)


# =============================================================================
# Chat Schemas
# =============================================================================


class SourceCitation(BaseModel):
    """A single source citation returned alongside a chat answer.

    Identifies which scraped page (and which chunk of text) was used
    as evidence for the generated answer.
    """

    url: str = Field(..., description="The source page URL.")
    title: str = Field(..., description="The source page title.")
    snippet: str = Field(
        ...,
        description="First 200 characters of the chunk text used as evidence.",
    )


class ChatRequest(BaseModel):
    """Request body for ``POST /api/chat``."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="The user's natural language question.",
        examples=["What are Python decorators?"],
    )
    job_id: str | None = Field(
        default=None,
        description=(
            "Scope retrieval to a specific scrape job. "
            "If null, searches all indexed sources."
        ),
    )


class ChatResponse(BaseModel):
    """Response body for ``POST /api/chat``."""

    answer: str = Field(..., description="The generated answer (may contain markdown).")
    sources: list[SourceCitation] = Field(
        default_factory=list,
        description="Source citations referenced in the answer.",
    )


class ChatMessageSchema(BaseModel):
    """A single persisted chat message, used in history responses."""

    id: str
    role: str
    content: str
    sources: list[SourceCitation] | None = None
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    """Response body for ``GET /api/chat/{job_id}/history``."""

    messages: list[ChatMessageSchema] = Field(default_factory=list)


# =============================================================================
# Source Management Schemas
# =============================================================================


class SourceSummary(BaseModel):
    """Summary of a scrape job, used in the source listing."""

    job_id: str
    seed_url: str
    domain: str
    status: str
    pages_scraped: int
    total_chunks: int
    created_at: datetime


class SourceListResponse(BaseModel):
    """Response body for ``GET /api/sources``."""

    jobs: list[SourceSummary] = Field(default_factory=list)


class SourcePagesResponse(BaseModel):
    """Response body for ``GET /api/sources/{job_id}/pages``."""

    pages: list[PageInfo] = Field(default_factory=list)


# =============================================================================
# Error Schema
# =============================================================================


class ErrorResponse(BaseModel):
    """Standard error response body returned on 4xx/5xx errors."""

    detail: str = Field(..., description="Human-readable error description.")



