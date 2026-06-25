"""FastAPI Router for chat and RAG query endpoints.

Provides routes to submit questions to a scraped source (POST /chat) and retrieve
conversation history for a job context (GET /chat/history/{job_id}).
"""

import asyncio
from datetime import datetime
import json
import logging
from typing import Any, Union

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.models.database import ChatMessage, ScrapeJob, QuestionSuggestion

# Configure module-level logger
logger = logging.getLogger(__name__)

# Initialize FastAPI router
router = APIRouter()


# =============================================================================
# Custom API Schemas for Exact Citations Format Matching
# =============================================================================

class CitationInfo(BaseModel):
    """Source page citation details."""
    source_url: str = Field(..., description="The source page URL.")
    page_title: str = Field(..., description="The source page title.")


class ChatWebRequest(BaseModel):
    """Incoming request body for POST /chat."""
    job_id: Union[str, None] = Field(
        default=None,
        description="The scrape job UUID to scope retrieval. Use null for global search."
    )
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="The user's natural language question."
    )


class ChatWebResponse(BaseModel):
    """Outgoing response body for POST /chat containing answer and citations."""
    answer: str = Field(..., description="The generated response text (may contain markdown).")
    citations: list[CitationInfo] = Field(
        default_factory=list,
        description="List of sources cited in the response."
    )


class WebChatMessage(BaseModel):
    """A single chat message in the session history."""
    id: str
    role: str
    content: str
    citations: list[CitationInfo] | None = None
    created_at: datetime


class WebChatHistoryResponse(BaseModel):
    """Response containing list of previous chat messages."""
    messages: list[WebChatMessage] = Field(default_factory=list)


class SuggestionResponse(BaseModel):
    """Response body for GET /api/suggestions/{job_id}."""
    job_id: str
    suggestions: list[str] = Field(default_factory=list)


# =============================================================================
# Router Endpoints
# =============================================================================

@router.post(
    "/chat",
    response_model=ChatWebResponse,
    responses={
        400: {"description": "Job not completed"},
        404: {"description": "Job not found"},
        503: {"description": "AI model generation error"}
    },
    summary="Ask a question grounded in scraped website content"
)
async def ask_question(
    request: ChatWebRequest,
    db: AsyncSession = Depends(get_db)
) -> ChatWebResponse:
    """Submit a question to a scraped source.

    Validates job status, triggers RAG context lookup and Gemini generation, and
    saves the conversation history in a single transaction.
    """
    question_str = request.question.strip()
    if not question_str:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Question cannot be empty or whitespace-only."
        )

    # 1. Validate ScrapeJob context if job_id is provided
    if request.job_id is not None:
        stmt = select(ScrapeJob).where(ScrapeJob.id == request.job_id)
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scrape job '{request.job_id}' not found."
            )
        if job.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Source is still being processed (current status: '{job.status}'). Please wait."
            )

    logger.info("Executing RAG pipeline for query: '%s'", question_str)

    # 2. Invoke RAG Generation pipeline
    try:
        from app.services.rag import generate_answer
        # generate_answer is now an async coroutine; await it directly
        rag_res = await generate_answer(request.job_id, question_str)
    except Exception as e:
        logger.error("RAG pipeline execution failed: %s", e)
        # Map known errors or re-raise as Service Unavailable (503)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )

    # 3. Persist history in a single atomic database transaction
    try:
        # User message
        user_msg = ChatMessage(
            job_id=request.job_id,
            role="user",
            content=question_str
        )
        # Assistant message
        assistant_msg = ChatMessage(
            job_id=request.job_id,
            role="assistant",
            content=rag_res["answer"],
            sources=json.dumps(rag_res["citations"])
        )

        db.add(user_msg)
        db.add(assistant_msg)
        await db.flush()  # Commits automatically on request completion via get_db middleware
    except Exception as db_err:
        logger.exception("Failed to write conversation history to SQLite: %s", db_err)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save chat history to database."
        )

    # 4. Map citations results to schema format
    web_citations = [
        CitationInfo(
            source_url=c["source_url"],
            page_title=c["page_title"]
        )
        for c in rag_res["citations"]
    ]

    return ChatWebResponse(
        answer=rag_res["answer"],
        citations=web_citations
    )


@router.get(
    "/chat/history/{job_id}",
    response_model=WebChatHistoryResponse,
    responses={404: {"description": "Job not found"}},
    summary="Retrieve chat history for a scrape job context"
)
@router.get(
    "/chat/{job_id}/history",
    response_model=WebChatHistoryResponse,
    include_in_schema=False  # Hide duplicate endpoint from openapi docs
)
async def get_chat_history(
    job_id: str,
    db: AsyncSession = Depends(get_db)
) -> WebChatHistoryResponse:
    """Retrieve all past conversation messages scoped to a specific job context.

    Use 'global' or 'null' to fetch history for all-sources global chat.
    """
    # 1. Parse job scope
    is_global = job_id.lower() in ("global", "null", "none")

    if not is_global:
        # Check that job actually exists
        stmt = select(ScrapeJob).where(ScrapeJob.id == job_id)
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scrape job context '{job_id}' not found."
            )

    # 2. Query chat history
    if is_global:
        history_stmt = select(ChatMessage).where(ChatMessage.job_id.is_(None)).order_by(
            ChatMessage.created_at.asc()
        )
    else:
        history_stmt = select(ChatMessage).where(ChatMessage.job_id == job_id).order_by(
            ChatMessage.created_at.asc()
        )

    history_res = await db.execute(history_stmt)
    db_messages = history_res.scalars().all()

    # 3. Format response message models
    web_messages = []
    for msg in db_messages:
        citations = []
        if msg.sources:
            try:
                parsed_sources = json.loads(msg.sources)
                citations = [
                    CitationInfo(
                        source_url=s["source_url"],
                        page_title=s["page_title"]
                    )
                    for s in parsed_sources
                ]
            except Exception:
                pass

        web_messages.append(
            WebChatMessage(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                citations=citations if msg.role == "assistant" else None,
                created_at=msg.created_at
            )
        )

    return WebChatHistoryResponse(messages=web_messages)


@router.get(
    "/suggestions/{job_id}",
    response_model=SuggestionResponse,
    responses={
        404: {"description": "Job not found"}
    },
    summary="Retrieve suggested questions for a scrape job context"
)
async def get_suggestions(
    job_id: str,
    db: AsyncSession = Depends(get_db)
) -> SuggestionResponse:
    """Retrieve exactly 10 AI suggested questions for a completed scrape job.

    Uses a database caching strategy to ensure Groq is only called once.
    """
    # 1. Handle global or null scope
    if job_id.lower() in ("global", "null", "none"):
        return SuggestionResponse(job_id=job_id, suggestions=[])

    # 2. Check cache first
    stmt = select(QuestionSuggestion).where(QuestionSuggestion.job_id == job_id).order_by(
        QuestionSuggestion.created_at.asc()
    )
    res = await db.execute(stmt)
    db_suggestions = res.scalars().all()

    if db_suggestions:
        logger.info("[%s] Returning %d cached suggested questions from DB.", job_id, len(db_suggestions))
        return SuggestionResponse(
            job_id=job_id,
            suggestions=[s.question for s in db_suggestions]
        )

    # 3. If no suggestions exist, verify the job is completed
    job_stmt = select(ScrapeJob).where(ScrapeJob.id == job_id)
    job_res = await db.execute(job_stmt)
    job = job_res.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scrape job '{job_id}' not found."
        )

    if job.status != "completed":
        # Job not finished or failed; suggestions aren't ready/applicable
        return SuggestionResponse(job_id=job_id, suggestions=[])

    # 4. Generate on-demand once if missing (failsafe for pre-existing or failed background generation)
    logger.info("[%s] Suggestions cache miss for completed job. Generating on-demand...", job_id)
    try:
        from app.services.vector_store import get_collection
        collection = get_collection(job_id)
        # Limit retrieval to 25 representative documents
        data = collection.get(limit=25)
        documents = data.get("documents", [])

        if documents:
            full_text = "\n\n".join(documents)
            from app.services.groq_service import GroqService
            groq_svc = GroqService()
            suggestions = await groq_svc.generate_suggestions(full_text)

            if suggestions:
                # Store generated suggestions in database
                for sugg_text in suggestions:
                    db_sugg = QuestionSuggestion(
                        job_id=job_id,
                        question=sugg_text
                    )
                    db.add(db_sugg)
                await db.commit()
                logger.info("[%s] Stored %d generated questions in DB.", job_id, len(suggestions))
                return SuggestionResponse(job_id=job_id, suggestions=suggestions)
    except Exception as e:
        logger.warning("[%s] Failed to generate suggested questions on-demand: %s", job_id, e)

    return SuggestionResponse(job_id=job_id, suggestions=[])


@router.get(
    "/debug/gemini",
    tags=["Debug"],
    summary="Debug Gemini API connectivity"
)
async def debug_gemini() -> dict[str, Any]:
    """Temporary diagnostic endpoint to audit Gemini API connectivity.

    Verifies key presence, client initialization, and test prompt generation.
    """
    from app.core.config import settings
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig
    import time

    api_key = settings.GEMINI_API_KEY.strip()
    key_loaded = bool(api_key)
    model_name = settings.GEMINI_MODEL

    if not key_loaded:
        return {
            "api_key_loaded": False,
            "model": model_name,
            "error": "GEMINI_API_KEY environment variable is missing or empty."
        }

    try:
        # Configure API key
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)

        # Generate a test request
        config = GenerationConfig(
            temperature=0.0,
            max_output_tokens=10,
        )
        start_time = time.time()
        response = model.generate_content("Reply with the word SUCCESS", generation_config=config)
        elapsed = time.time() - start_time

        response_text = response.text.strip() if response.text else ""

        return {
            "api_key_loaded": True,
            "model": model_name,
            "response": response_text,
            "elapsed_seconds": round(elapsed, 3)
        }
    except Exception as e:
        logger.exception("Gemini debug connectivity test failed")
        return {
            "api_key_loaded": True,
            "model": model_name,
            "error": str(e),
            "error_type": type(e).__name__
        }
