"""FastAPI Router for chat and RAG query endpoints.

Provides routes to submit questions to a scraped source (POST /chat),
stream responses via SSE (POST /chat/stream), and retrieve
conversation history for a job context (GET /chat/history/{job_id}).
"""

import asyncio
from datetime import datetime
import json
import logging
import time
import uuid
from typing import Any, Union

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.models.database import ChatMessage, ScrapeJob

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

    # 1. Conversation routing — short-circuit common intents before hitting RAG
    from app.services.conversation_router import detect_intent, build_response as build_conv_response

    intent = detect_intent(question_str)
    if intent:
        # Resolve source context so the greeting can mention the active site
        source_title: str | None = None
        source_url: str | None = None
        if request.job_id is not None:
            try:
                stmt_ctx = select(ScrapeJob).where(ScrapeJob.id == request.job_id)
                res_ctx = await db.execute(stmt_ctx)
                job_ctx = res_ctx.scalar_one_or_none()
                if job_ctx:
                    source_title = job_ctx.domain or None
                    source_url = job_ctx.seed_url or None
            except Exception:
                pass  # Non-fatal; greeting still works without context

        conv_answer = build_conv_response(
            intent,
            source_title=source_title,
            source_url=source_url,
        )
        logger.info(
            "Conversation router matched intent '%s' — skipping RAG pipeline.", intent
        )

        # Persist to chat history (no citations for conversational replies)
        try:
            db.add(ChatMessage(job_id=request.job_id, role="user", content=question_str))
            db.add(ChatMessage(job_id=request.job_id, role="assistant", content=conv_answer, sources="[]"))
            await db.flush()
        except Exception as hist_err:
            logger.warning("Failed to persist conversational message history: %s", hist_err)
            await db.rollback()

        return ChatWebResponse(answer=conv_answer, citations=[])

    # 2. Validate ScrapeJob context if job_id is provided
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

    # 3. Invoke RAG Generation pipeline
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

    # 4. Persist history in a single atomic database transaction
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

    # 5. Map citations results to schema format
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


# =============================================================================
# Streaming SSE Endpoint
# =============================================================================

@router.post(
    "/chat/stream",
    summary="Stream a RAG-grounded answer via Server-Sent Events",
    responses={
        400: {"description": "Job not completed"},
        404: {"description": "Job not found"},
    },
)
async def stream_chat(
    request_body: ChatWebRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Stream an SSE response for a chat question.

    Returns a ``text/event-stream`` response with lifecycle events:
    status, start, delta, citations, done, aborted, interrupted, error, heartbeat.
    """
    question_str = request_body.question.strip()
    if not question_str:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Question cannot be empty or whitespace-only.",
        )

    # Pre-validate job before starting the stream
    if request_body.job_id is not None:
        stmt = select(ScrapeJob).where(ScrapeJob.id == request_body.job_id)
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scrape job '{request_body.job_id}' not found.",
            )
        if job.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Source is still being processed (current status: '{job.status}'). Please wait.",
            )

    # Check conversation router first
    from app.services.conversation_router import detect_intent, build_response as build_conv_response

    intent = detect_intent(question_str)
    conv_answer: str | None = None

    if intent:
        source_title: str | None = None
        source_url: str | None = None
        if request_body.job_id is not None:
            try:
                stmt_ctx = select(ScrapeJob).where(ScrapeJob.id == request_body.job_id)
                res_ctx = await db.execute(stmt_ctx)
                job_ctx = res_ctx.scalar_one_or_none()
                if job_ctx:
                    source_title = job_ctx.domain or None
                    source_url = job_ctx.seed_url or None
            except Exception:
                pass

        conv_answer = build_conv_response(
            intent,
            source_title=source_title,
            source_url=source_url,
        )
        logger.info(
            "[Stream] Conversation router matched intent '%s'.", intent,
        )

    # Generate unique IDs for this stream
    request_id = uuid.uuid4().hex[:12]
    stream_id = uuid.uuid4().hex[:12]

    async def sse_generator():
        """Inner async generator producing SSE-formatted text lines."""
        event_counter = 0
        seq_counter = 0
        accumulated_answer = ""
        accumulated_citations: list[dict] = []
        model_used = ""
        metrics_data: dict = {}
        gen_start = time.time()
        heartbeat_task = None
        stream_completed = False

        def _build_event(event_name: str, data: dict) -> str:
            """Format a single SSE event packet with metadata."""
            nonlocal event_counter, seq_counter
            event_counter += 1
            seq_counter += 1
            payload = {
                "event_id": event_counter,
                "stream_id": stream_id,
                "request_id": request_id,
                "seq": seq_counter,
                **data,
            }
            return f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"

        # Heartbeat background task
        heartbeat_active = True

        async def _heartbeat():
            nonlocal event_counter, seq_counter
            while heartbeat_active:
                await asyncio.sleep(10)
                if not heartbeat_active:
                    break
                event_counter += 1
                payload = {
                    "event_id": event_counter,
                    "stream_id": stream_id,
                    "request_id": request_id,
                    "seq": 0,  # Heartbeats don't increment seq
                }
                yield f"event: heartbeat\ndata: {json.dumps(payload)}\n\n"

        try:
            # Handle conversation router short-circuit
            if conv_answer is not None:
                yield _build_event("start", {"model": "conversation_router"})
                yield _build_event("delta", {"text": conv_answer})
                yield _build_event("citations", {"citations": []})

                gen_ms = (time.time() - gen_start) * 1000
                yield _build_event("done", {
                    "model": "conversation_router",
                    "finish_reason": "stop",
                    "usage": {
                        "generation_ms": round(gen_ms, 1),
                        "characters_streamed": len(conv_answer),
                        "tokens_streamed": len(conv_answer) // 4,
                        "tokens_per_second": 0,
                    },
                })

                # Persist
                try:
                    from app.core.database import async_session_factory
                    async with async_session_factory() as persist_db:
                        persist_db.add(ChatMessage(
                            job_id=request_body.job_id,
                            role="user",
                            content=question_str,
                        ))
                        persist_db.add(ChatMessage(
                            job_id=request_body.job_id,
                            role="assistant",
                            content=conv_answer,
                            sources="[]",
                        ))
                        await persist_db.commit()
                except Exception as db_err:
                    logger.warning("[Stream] Failed to persist conv router history: %s", db_err)

                stream_completed = True
                return

            # Full RAG streaming pipeline
            from app.services.rag import generate_answer_stream

            async for item in generate_answer_stream(
                request_body.job_id, question_str, request_id,
            ):
                # Check for client disconnect
                if await request.is_disconnected():
                    logger.info("[Stream] Client disconnected. Emitting interrupted event.")

                    # Emit interrupted with accumulated data
                    yield _build_event("interrupted", {
                        "message": "Client disconnected",
                        "citations": accumulated_citations,
                    })

                    # Persist partial response
                    if accumulated_answer:
                        try:
                            from app.core.database import async_session_factory
                            from app.services.rag import clean_citations_from_text
                            async with async_session_factory() as persist_db:
                                clean_answer = clean_citations_from_text(accumulated_answer)
                                persist_db.add(ChatMessage(
                                    job_id=request_body.job_id,
                                    role="user",
                                    content=question_str,
                                ))
                                persist_db.add(ChatMessage(
                                    job_id=request_body.job_id,
                                    role="assistant",
                                    content=clean_answer,
                                    sources=json.dumps(accumulated_citations),
                                ))
                                await persist_db.commit()
                        except Exception as db_err:
                            logger.warning("[Stream] Failed to persist partial response: %s", db_err)
                    return

                event_name = item["event"]
                event_data = item["data"]

                if event_name == "status":
                    yield _build_event("status", {"text": event_data})
                elif event_name == "start":
                    model_used = event_data.get("model", "")
                    yield _build_event("start", {"model": model_used})
                elif event_name == "delta":
                    accumulated_answer += event_data.get("text", "")
                    yield _build_event("delta", event_data)
                elif event_name == "citations":
                    accumulated_citations = event_data.get("citations", [])
                    yield _build_event("citations", event_data)
                elif event_name == "metrics":
                    metrics_data = event_data
                elif event_name == "_final":
                    # Internal event — use for persistence but don't emit
                    final_answer = event_data.get("answer", accumulated_answer)
                    final_citations = event_data.get("citations", accumulated_citations)

                    # Persist to database
                    try:
                        from app.core.database import async_session_factory
                        async with async_session_factory() as persist_db:
                            persist_db.add(ChatMessage(
                                job_id=request_body.job_id,
                                role="user",
                                content=question_str,
                            ))
                            persist_db.add(ChatMessage(
                                job_id=request_body.job_id,
                                role="assistant",
                                content=final_answer,
                                sources=json.dumps(final_citations),
                            ))
                            await persist_db.commit()
                    except Exception as db_err:
                        logger.warning("[Stream] Failed to persist chat history: %s", db_err)

            # Emit done event
            gen_ms = (time.time() - gen_start) * 1000
            usage = metrics_data if metrics_data else {
                "generation_ms": round(gen_ms, 1),
                "characters_streamed": len(accumulated_answer),
                "tokens_streamed": len(accumulated_answer) // 4,
                "tokens_per_second": 0,
            }
            yield _build_event("done", {
                "model": model_used,
                "finish_reason": "stop",
                "usage": usage,
            })
            stream_completed = True

        except Exception as e:
            logger.exception("[Stream] SSE generator error: %s", e)
            yield _build_event("error", {"message": str(e)})

            # Persist partial response on error
            if accumulated_answer:
                try:
                    from app.core.database import async_session_factory
                    from app.services.rag import clean_citations_from_text
                    async with async_session_factory() as persist_db:
                        clean_answer = clean_citations_from_text(accumulated_answer)
                        persist_db.add(ChatMessage(
                            job_id=request_body.job_id,
                            role="user",
                            content=question_str,
                        ))
                        persist_db.add(ChatMessage(
                            job_id=request_body.job_id,
                            role="assistant",
                            content=clean_answer,
                            sources=json.dumps(accumulated_citations),
                        ))
                        await persist_db.commit()
                except Exception as db_err:
                    logger.warning("[Stream] Failed to persist error partial response: %s", db_err)

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
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


