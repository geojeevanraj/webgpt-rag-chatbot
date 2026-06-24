"""FastAPI Router for source management and metadata listing endpoints.

Provides routes to list all ingested sources/jobs (GET /sources) and query the
detailed page metrics of a specific source (GET /sources/{job_id}).
"""

import logging
from typing import Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.models.database import ScrapeJob, ScrapedPage
from app.models.schemas import ErrorResponse, PageInfo, SourcePagesResponse, SourceSummary

# Configure module-level logger
logger = logging.getLogger(__name__)

# Initialize FastAPI router
router = APIRouter()


# =============================================================================
# Custom API Schemas for Exact Domain/Page Metrics Matching
# =============================================================================

class PageSummary(BaseModel):
    """Sub-schema for page details within job detail response."""
    url: str = Field(..., description="The crawled URL.")
    title: str = Field(..., description="The page title.")
    depth: int = Field(..., description="Depth level from seed URL.")
    chunk_count: int = Field(..., description="Number of text chunks indexed.")


class SourceDetailResponse(BaseModel):
    """Response body for GET /api/sources/{job_id}."""
    job_id: str = Field(..., description="The job UUID.")
    domain: str = Field(..., description="The seed host domain.")
    pages: list[PageSummary] = Field(
        default_factory=list,
        description="List of crawled subpages belonging to the source."
    )


# =============================================================================
# Router Endpoints
# =============================================================================

@router.get(
    "/sources",
    response_model=list[SourceSummary],
    summary="List all scrape jobs/sources with pagination"
)
async def list_sources(
    limit: int = Query(default=10, ge=1, le=100, description="Max number of sources to return."),
    offset: int = Query(default=0, ge=0, description="Number of sources to skip."),
    db: AsyncSession = Depends(get_db)
) -> list[SourceSummary]:
    """Retrieve a list of all ingested scrape jobs/sources.

    Sorted by creation timestamp in descending order (newest first). Supports
    pagination via limit and offset parameters.
    """
    logger.info("Retrieving sources list (limit=%d, offset=%d)", limit, offset)

    try:
        # Query scrape jobs ordered by created_at DESC with pagination limits
        stmt = (
            select(ScrapeJob)
            .order_by(ScrapeJob.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await db.execute(stmt)
        jobs = res.scalars().all()

        return [
            SourceSummary(
                job_id=job.id,
                seed_url=job.seed_url,
                domain=job.domain,
                status=job.status,
                pages_scraped=job.pages_scraped,
                total_chunks=job.total_chunks,
                created_at=job.created_at
            )
            for job in jobs
        ]
    except Exception as e:
        logger.error("Failed to query sources list from database: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sources list."
        )


@router.get(
    "/sources/{job_id}",
    response_model=SourceDetailResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Retrieve detailed page metrics for a specific source"
)
async def get_source_details(
    job_id: str,
    db: AsyncSession = Depends(get_db)
) -> SourceDetailResponse:
    """Retrieve domain context and page crawling metrics for a scrape job."""
    logger.info("Retrieving detailed pages list for source: %s", job_id)

    # 1. Fetch parent job to verify source exists and obtain domain info
    stmt = select(ScrapeJob).where(ScrapeJob.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source job context '{job_id}' not found."
        )

    # 2. Fetch crawled page metrics ordered by depth and crawl time
    pages_stmt = (
        select(ScrapedPage)
        .where(ScrapedPage.job_id == job_id)
        .order_by(ScrapedPage.depth.asc(), ScrapedPage.scraped_at.asc())
    )
    pages_res = await db.execute(pages_stmt)
    pages = pages_res.scalars().all()

    # 3. Format response details
    web_pages = [
        PageSummary(
            url=p.url,
            title=p.title,
            depth=p.depth,
            chunk_count=p.chunk_count
        )
        for p in pages
    ]

    return SourceDetailResponse(
        job_id=job.id,
        domain=job.domain,
        pages=web_pages
    )


@router.get(
    "/sources/{job_id}/pages",
    response_model=SourcePagesResponse,
    include_in_schema=False
)
async def get_source_pages_legacy(
    job_id: str,
    db: AsyncSession = Depends(get_db)
) -> SourcePagesResponse:
    """Fallback route supporting legacy Phase 1 schemas.

    Resolves lists of full PageInfo objects under the legacy '/pages' suffix path.
    """
    # 1. Verify parent job exists
    stmt = select(ScrapeJob).where(ScrapeJob.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source job context '{job_id}' not found."
        )

    # 2. Query scraped pages
    pages_stmt = (
        select(ScrapedPage)
        .where(ScrapedPage.job_id == job_id)
        .order_by(ScrapedPage.depth.asc(), ScrapedPage.scraped_at.asc())
    )
    pages_res = await db.execute(pages_stmt)
    db_pages = pages_res.scalars().all()

    pages_info = [
        PageInfo(
            url=p.url,
            title=p.title,
            depth=p.depth,
            chunk_count=p.chunk_count,
            status=p.status,
            error_message=p.error_message
        )
        for p in db_pages
    ]

    return SourcePagesResponse(pages=pages_info)
