"""FastAPI Router for web scraping endpoints.

Provides routes to trigger ingestion jobs (POST /scrape), retrieve job status and
page crawling progress (GET /scrape/{job_id}), and delete scrape jobs and associated
data indexes (DELETE /scrape/{job_id}).
"""

import asyncio
from datetime import datetime, timezone
import ipaddress
import logging
import socket
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory, get_db
from app.models.database import ScrapeJob, ScrapedPage
from app.models.schemas import ErrorResponse, PageInfo, ScrapeRequest, ScrapeResponse, ScrapeStatusResponse

# Configure module-level logger
logger = logging.getLogger(__name__)

# Initialize FastAPI router
router = APIRouter()


def validate_url_ssrf(url: str) -> None:
    """Validate a URL against Server-Side Request Forgery (SSRF) vectors.

    Ensures the URL uses http/https, has a valid hostname, and resolves only to
    publicly routable IP addresses (rejecting private subnets like 127.0.0.0/8,
    10.0.0.0/8, 192.168.0.0/16, etc.).

    Args:
        url: The string URL to validate.

    Raises:
        ValueError: If validation fails.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only HTTP and HTTPS URLs are allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid URL: no hostname found.")

    try:
        # Perform DNS lookup to extract IP addresses
        addr_info = socket.getaddrinfo(hostname, None)
    except Exception as e:
        raise ValueError(f"DNS resolution failed for hostname '{hostname}'") from e

    # Audit all resolved IP addresses
    for family, _, _, _, sockaddr in addr_info:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
            # Prevent access to loopbacks, private networks, reserved scopes, and link-locals
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                raise ValueError("URLs pointing to private/internal networks are not allowed.")
        except ValueError as val_err:
            # Re-raise explicit SSRF messages
            if "private/internal" in str(val_err):
                raise val_err
            # Ignore invalid IP strings (e.g. scope ID issues in IPv6 sockaddr)
            pass


async def run_scrape_pipeline(
    job_id: str,
    seed_url: str,
    max_depth: int,
    max_pages: int
) -> None:
    """FastAPI BackgroundTask orchestrating the recursive scraping pipeline.

    Flow:
    1. Update ScrapeJob status in database to 'scraping'.
    2. Initialize ChromaDB vector collection.
    3. Run BFS crawler (scraper.py).
    4. On page scraped: clean HTML, chunk, embed, and index chunks into ChromaDB.
    5. Persist progress incrementally in SQLite.
    6. Complete job with 'completed' or 'failed' status depending on execution.

    Args:
        job_id: The UUID of the ScrapeJob.
        seed_url: The seed URL to begin scraping from.
        max_depth: Maximum BFS recursion depth.
        max_pages: Maximum successful pages to index.
    """
    logger.info("[%s] Starting background scrape pipeline for seed: %s", job_id, seed_url)

    # 1. Update job status to 'scraping'
    async with async_session_factory() as session:
        try:
            stmt = select(ScrapeJob).where(ScrapeJob.id == job_id).with_for_update()
            res = await session.execute(stmt)
            job = res.scalar_one_or_none()
            if not job:
                logger.error("[%s] ScrapeJob not found in database.", job_id)
                return

            job.status = "scraping"
            job.updated_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info("[%s] Status updated to 'scraping'", job_id)
        except Exception as e:
            logger.exception("[%s] Database error during pipeline startup: %s", job_id, e)
            await session.rollback()
            return

    # 2. Create ChromaDB collection
    try:
        from app.services.vector_store import create_collection
        # Running synchronous persistent client collection creation inside a thread pool
        await asyncio.to_thread(create_collection, job_id)
        logger.info("[%s] Vector store collection created", job_id)
    except Exception as e:
        logger.exception("[%s] Vector store collection initialization failed: %s", job_id, e)
        async with async_session_factory() as session:
            stmt = select(ScrapeJob).where(ScrapeJob.id == job_id).with_for_update()
            res = await session.execute(stmt)
            job = res.scalar_one()
            job.status = "failed"
            job.error_message = f"Failed to initialize vector database collection: {e}"
            job.updated_at = datetime.now(timezone.utc)
            await session.commit()
        return

    # Callback executed by scraper.py after each page attempt
    async def on_page_scraped(
        url: str,
        title: str,
        html: str,
        depth: int,
        status_str: str,
        error_message: str | None
    ) -> None:
        async with async_session_factory() as callback_session:
            try:
                chunk_count = 0

                # Process successfully scraped HTML
                if status_str == "scraped":
                    from app.services.chunker import chunk
                    from app.services.vector_store import add_chunks

                    # Clean, extract, and chunk text content (runs synchronously)
                    chunks = chunk(html, url, title, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)

                    if chunks:
                        chunk_count = len(chunks)
                        # Embed and index text vectors (runs CPU-heavy inference inside a thread pool)
                        await asyncio.to_thread(add_chunks, job_id, chunks)

                # Persist ScrapedPage progress immediately
                db_page = ScrapedPage(
                    job_id=job_id,
                    url=url,
                    title=title,
                    depth=depth,
                    status=status_str,
                    error_message=error_message,
                    chunk_count=chunk_count
                )
                callback_session.add(db_page)

                # Update parent job counters with lock
                stmt = select(ScrapeJob).where(ScrapeJob.id == job_id).with_for_update()
                res = await callback_session.execute(stmt)
                job = res.scalar_one_or_none()

                if job:
                    if status_str == "scraped":
                        job.pages_scraped += 1
                        job.total_chunks += chunk_count
                    else:
                        job.pages_failed += 1
                    job.updated_at = datetime.now(timezone.utc)

                await callback_session.commit()
                logger.info(
                    "[%s] Crawled and indexed: %s (status=%s, chunks=%d)",
                    job_id, url, status_str, chunk_count
                )
            except Exception as callback_err:
                logger.error(
                    "[%s] Exception occurred in callback handler for URL %s: %s",
                    job_id, url, callback_err
                )
                await callback_session.rollback()

    # 3. Trigger BFS Scraper
    try:
        from app.services.scraper import scrape
        await scrape(seed_url, max_depth, max_pages, job_id, on_page_scraped)

        # 4. Successful crawler completion
        async with async_session_factory() as session:
            stmt = select(ScrapeJob).where(ScrapeJob.id == job_id).with_for_update()
            res = await session.execute(stmt)
            job = res.scalar_one()
            job.status = "completed"
            job.updated_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info("[%s] Scrape pipeline completed successfully", job_id)

        # 5. Generate AI suggested questions using Groq service (non-blocking / error-safe)
        try:
            from app.services.vector_store import get_collection
            collection = get_collection(job_id)
            # Limit retrieval to 25 representative documents to save API tokens
            data = collection.get(limit=25)
            documents = data.get("documents", [])

            if documents:
                full_text = "\n\n".join(documents)
                from app.services.groq_service import GroqService
                groq_svc = GroqService()
                suggestions = await groq_svc.generate_suggestions(full_text)

                if suggestions:
                    async with async_session_factory() as session_sugg:
                        from app.models.database import QuestionSuggestion
                        for sugg_text in suggestions:
                            db_sugg = QuestionSuggestion(
                                job_id=job_id,
                                question=sugg_text
                            )
                            session_sugg.add(db_sugg)
                        await session_sugg.commit()
                        logger.info("[%s] Successfully generated and stored %d suggested questions.", job_id, len(suggestions))
                else:
                    logger.warning("[%s] No suggested questions were generated by Groq.", job_id)
            else:
                logger.warning("[%s] No documents found in vector store, skipping suggestions.", job_id)
        except Exception as groq_err:
            logger.warning("[%s] Failed to generate/store suggested questions: %s", job_id, groq_err)

    except Exception as scrape_err:
        # 5. Handle unhandled pipeline or network-wide crashes
        logger.exception("[%s] Scrape pipeline crashed: %s", job_id, scrape_err)
        async with async_session_factory() as session:
            stmt = select(ScrapeJob).where(ScrapeJob.id == job_id).with_for_update()
            res = await session.execute(stmt)
            job = res.scalar_one()
            job.status = "failed"
            job.error_message = f"Scrape pipeline crashed: {scrape_err}"
            job.updated_at = datetime.now(timezone.utc)
            await session.commit()


@router.post(
    "/scrape",
    response_model=ScrapeResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={422: {"model": ErrorResponse}},
    summary="Submit a URL to initiate a recursive scraping job"
)
async def start_scrape(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> ScrapeResponse:
    """Submit a website URL to recursively crawl and index its pages.

    Validates URL hosts against SSRF vectors. If validated, inserts a pending job
    record and delegates execution to a FastAPI BackgroundTask.
    """
    seed_url_str = str(request.url)

    # 1. Enforce Server-Side Request Forgery protection checks
    try:
        validate_url_ssrf(seed_url_str)
    except ValueError as e:
        logger.warning("SSRF block triggered on URL submission: %s", e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"URL validation failed: {e}"
        )

    # 2. Extract domain name for storage categorization
    parsed = urlparse(seed_url_str)
    domain = parsed.hostname or "unknown"

    # 3. Create ScrapeJob DB record (Default status is pending)
    job = ScrapeJob(
        seed_url=seed_url_str,
        domain=domain,
        max_depth=request.max_depth,
        max_pages=request.max_pages
    )
    db.add(job)
    await db.flush()  # Populates job.id and timestamp columns

    logger.info("[%s] Created scrape job for %s", job.id, seed_url_str)

    # 4. Schedule background scraping pipeline
    background_tasks.add_task(
        run_scrape_pipeline,
        job.id,
        seed_url_str,
        request.max_depth,
        request.max_pages
    )

    return ScrapeResponse(
        job_id=job.id,
        status=job.status,
        seed_url=job.seed_url,
        created_at=job.created_at
    )


@router.get(
    "/scrape/{job_id}",
    response_model=ScrapeStatusResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Retrieve details and progress of a scrape job"
)
@router.get(
    "/scrape/{job_id}/status",
    response_model=ScrapeStatusResponse,
    include_in_schema=False  # Hide duplicate endpoint from openapi docs
)
async def get_scrape_status(
    job_id: str,
    db: AsyncSession = Depends(get_db)
) -> ScrapeStatusResponse:
    """Retrieve full progress status for a scrape job and list crawled pages."""
    # 1. Query parent job
    stmt = select(ScrapeJob).where(ScrapeJob.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scrape job '{job_id}' not found."
        )

    # 2. Query individual scraped page lists
    page_stmt = select(ScrapedPage).where(ScrapedPage.job_id == job_id).order_by(
        ScrapedPage.depth,
        ScrapedPage.scraped_at
    )
    page_res = await db.execute(page_stmt)
    db_pages = page_res.scalars().all()

    # 3. Serialize response schema
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

    return ScrapeStatusResponse(
        job_id=job.id,
        seed_url=job.seed_url,
        domain=job.domain,
        status=job.status,
        max_depth=job.max_depth,
        max_pages=job.max_pages,
        pages_scraped=job.pages_scraped,
        pages_failed=job.pages_failed,
        total_chunks=job.total_chunks,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
        pages=pages_info
    )


@router.delete(
    "/scrape/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
    summary="Delete a scrape job and purge associated database and vector records"
)
async def delete_scrape(
    job_id: str,
    db: AsyncSession = Depends(get_db)
) -> Response:
    """Delete a scrape job.

    Deletes the vector store collection from ChromaDB and removes SQLite records.
    Database cascade triggers automatically purge pages and chat messages.
    """
    # 1. Verify job exists
    stmt = select(ScrapeJob).where(ScrapeJob.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scrape job '{job_id}' not found."
        )

    logger.info("[%s] Purging job and all associated records", job_id)

    # 2. Delete ChromaDB collection
    try:
        from app.services.vector_store import delete_collection
        # delete_collection performs disk IO; execute in thread pool
        await asyncio.to_thread(delete_collection, job_id)
    except Exception as e:
        logger.error("[%s] Failed to delete ChromaDB collection: %s", job_id, e)
        # We log and proceed so SQLite cascade deletion isn't blocked by ChromaDB offline states

    # 3. Delete database record
    # Declared cascade rules automatically purge scraped_pages and chat_messages rows
    await db.delete(job)
    await db.commit()

    logger.info("[%s] Purge complete.", job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
