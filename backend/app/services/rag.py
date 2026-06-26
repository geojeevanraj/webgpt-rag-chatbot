"""Retrieval-Augmented Generation (RAG) service.

This module orchestrates the RAG pipeline: embedding user questions, querying
the vector store, constructing prompts with retrieved contexts, invoking the
Gemini model, and extracting cited sources from the generated answers.

Quality improvements included here:
- Empty knowledge-base detection (checks vector store directly, skips embedder)
- Metadata-based reranking for general-information queries (no cosine-score changes)
- Grounded insufficient-information fallback that surfaces real indexed page titles
"""

import logging
import re
import time
from typing import Any, Union

from app.core.config import settings
from app.services.embedder import embed_text
from app.services.vector_store import (
    collection_exists,
    get_client,
    similarity_search,
)

# ---------------------------------------------------------------------------
# Reranking constants
# ---------------------------------------------------------------------------

# Query prefixes that signal the user wants a high-level overview or general info.
_GENERAL_INFO_PREFIXES: tuple[str, ...] = (
    "what is", "what's", "who is", "who's",
    "tell me about", "overview", "introduction",
    "describe", "explain", "summary", "about",
    "company",
)

# URL / title substrings that indicate a page is a good landing or about page.
_PRIORITY_PAGE_SIGNALS: tuple[str, ...] = (
    "about", "home", "overview", "company",
    "introduction", "index",
)

# Configure module-level logger
logger = logging.getLogger(__name__)


def _has_any_indexed_content(job_id: Union[str, None]) -> bool:
    """Check whether the vector store contains at least one indexed chunk.

    This deliberately avoids generating any embeddings — it only inspects the
    ChromaDB collection metadata.  It is the authoritative source of truth for
    the empty-knowledge-base guard.

    Args:
        job_id: Specific job UUID to check, or None to check all collections.

    Returns:
        True if at least one document exists in the relevant collection(s).
    """
    try:
        client = get_client()
        collections = client.list_collections()
        job_col_names = []
        for col in collections:
            name = col if isinstance(col, str) else getattr(col, "name", "")
            if name.startswith("job_"):
                job_col_names.append(name)

        if not job_col_names:
            return False

        for col_name in job_col_names:
            j_id = col_name[4:]
            # If scoped to a specific job, skip others
            if job_id is not None and j_id != job_id:
                continue
            try:
                col = client.get_collection(name=col_name)
                if col.count() > 0:
                    return True
            except Exception:
                continue
        return False
    except Exception as e:
        logger.warning("Could not verify indexed content presence: %s", e)
        return False


def _is_general_info_query(question: str) -> bool:
    """Return True if the question appears to be a general-information / overview query.

    Matching is done on lowercased text only; no regex is needed because we
    only look at the start of the question.
    """
    q = question.strip().lower()
    return any(q.startswith(prefix) for prefix in _GENERAL_INFO_PREFIXES)


def _rerank_chunks(
    chunks: list[dict[str, Any]],
    question: str,
) -> list[dict[str, Any]]:
    """Reorder retrieved chunks by metadata priority for general-info queries.

    Only activated for questions that match :func:`_is_general_info_query`.
    Chunks are split into two groups:

    * **Priority group** — pages whose title or URL contains one of the
      signals in ``_PRIORITY_PAGE_SIGNALS`` (about, home, overview, …).
    * **Normal group** — all other chunks.

    Within each group, the original cosine-distance order is preserved.
    The final list is ``priority_group + normal_group``.

    Cosine-distance values are never modified.

    Args:
        chunks: Top-K chunks already filtered by the relevance threshold.
        question: The user's question (used to decide whether reranking applies).

    Returns:
        Reranked chunk list (may be identical to input if reranking does not apply).
    """
    if not _is_general_info_query(question) or not chunks:
        return chunks

    priority: list[dict[str, Any]] = []
    normal: list[dict[str, Any]] = []

    for chunk in chunks:
        title = (chunk.get("page_title") or "").lower()
        url = (chunk.get("source_url") or "").lower()
        combined = title + " " + url
        if any(signal in combined for signal in _PRIORITY_PAGE_SIGNALS):
            priority.append(chunk)
        else:
            normal.append(chunk)

    if priority:
        logger.info(
            "Reranking: promoted %d priority chunk(s) for general-info query '%s'",
            len(priority),
            question[:80],
        )

    return priority + normal


def _collect_indexed_page_titles(job_id: Union[str, None]) -> list[str]:
    """Return a deduplicated list of page titles from the indexed collection(s).

    Used to populate the grounded insufficient-info fallback response with
    real page names rather than generic placeholders.

    Limits to the first 10 titles to keep the response concise.
    """
    try:
        client = get_client()
        collections = client.list_collections()
        titles: list[str] = []
        seen: set[str] = set()

        for col in collections:
            col_name = col if isinstance(col, str) else getattr(col, "name", "")
            if not col_name.startswith("job_"):
                continue
            j_id = col_name[4:]
            if job_id is not None and j_id != job_id:
                continue
            try:
                collection = client.get_collection(name=col_name)
                results = collection.get(limit=200, include=["metadatas"])
                for meta in (results.get("metadatas") or []):
                    t = (meta or {}).get("page_title", "")
                    if t and t not in seen:
                        seen.add(t)
                        titles.append(t)
                        if len(titles) >= 10:
                            break
            except Exception:
                continue
            if len(titles) >= 10:
                break

        return titles
    except Exception as e:
        logger.warning("Could not collect indexed page titles for fallback: %s", e)
        return []


def _build_insufficient_info_response(
    question: str,
    job_id: Union[str, None],
) -> str:
    """Build a grounded fallback response when retrieval returns no useful chunks.

    Never calls the LLM; never hallucinate.
    Populates suggestions from real indexed page titles when available.

    Args:
        question: The user's original question.
        job_id: Scoped job UUID (or None for global).

    Returns:
        A markdown-formatted fallback response string.
    """
    # Derive a short topic label from the question for the message
    topic = question.strip().rstrip("?.").strip()
    if len(topic) > 80:
        topic = topic[:77] + "…"

    page_titles = _collect_indexed_page_titles(job_id)

    if page_titles:
        bullets = "\n".join(f"• {t}" for t in page_titles)
        suggestions_block = (
            "You can try asking about:\n\n"
            f"{bullets}"
        )
    else:
        suggestions_block = (
            "You can try asking about:\n\n"
            "• About Us\n"
            "• Services\n"
            "• Products\n"
            "• Technologies\n"
            "• Careers"
        )

    return (
        f'I couldn\'t find enough information about **"{topic}"** '
        "in the indexed pages of this website.\n\n"
        f"{suggestions_block}\n\n"
        "> **Tip:** Try scraping more pages from the website or selecting "
        "another indexed source."
    )


def retrieve_context(
    job_id: Union[str, None],
    question: str,
    top_k: int = 5
) -> list[dict[str, Any]]:
    """Retrieve relevant text chunks from ChromaDB for the user question.

    If job_id is provided, queries that specific collection. If job_id is None,
    queries all collections matching the pattern "job_{job_id}", merges the results,
    and returns the overall top-K matches.

    Chunks exceeding the settings.RELEVANCE_THRESHOLD are filtered out.
    Results are then optionally reranked by metadata for general-info queries.

    Args:
        job_id: The UUID of the scrape job, or None to search globally.
        question: The user's question.
        top_k: Max number of chunks to return. Default: 5.

    Returns:
        A list of matching chunk dictionaries sorted by distance (ascending),
        with priority pages promoted for general-information queries.
    """
    # 1. Embed the query question
    logger.info("Generating embedding for search query...")
    query_embedding = embed_text(question)

    raw_chunks: list[dict[str, Any]] = []

    # 2. Query specific collection or all collections
    if job_id is not None:
        if not collection_exists(job_id):
            logger.warning("Retrieval skipped: collection for job_%s does not exist", job_id)
            return []
        raw_chunks = similarity_search(job_id, query_embedding, top_k=top_k)
    else:
        # Global search: query all active job collections
        logger.info("Performing global search across all vector store collections...")
        client = get_client()
        try:
            collections = client.list_collections()
            job_collection_names = []
            for col in collections:
                col_name = col if isinstance(col, str) else getattr(col, "name", "")
                if col_name.startswith("job_"):
                    job_collection_names.append(col_name)

            for col_name in job_collection_names:
                # Extract UUID from "job_UUID"
                j_id = col_name[4:]
                chunks = similarity_search(j_id, query_embedding, top_k=top_k)
                raw_chunks.extend(chunks)

            # Re-sort combined results by distance ascending (closest first)
            raw_chunks.sort(key=lambda x: x["distance"])
        except Exception as e:
            logger.error("Failed to fetch collections list for global search: %s", e)
            raise RuntimeError(f"Global similarity search failed: {e}") from e

    # 3. Filter chunks based on the configured cosine distance threshold
    filtered_chunks = [
        c for c in raw_chunks
        if c["distance"] <= settings.RELEVANCE_THRESHOLD
    ]

    logger.info(
        "Retrieved %d chunks (filtered from %d raw matches using threshold %.2f)",
        len(filtered_chunks),
        len(raw_chunks),
        settings.RELEVANCE_THRESHOLD
    )

    # 4. Apply metadata reranking for general-information queries
    reranked = _rerank_chunks(filtered_chunks[:top_k], question)

    return reranked


def build_context(chunks: list[dict[str, Any]]) -> str:
    """Format a list of text chunks into a structured context block for the LLM.

    Each block is indexed sequentially: [Source N] (from: Title - URL): Content

    Args:
        chunks: List of chunk dictionaries.

    Returns:
        A formatted string context block.
    """
    context_blocks = []
    for idx, c in enumerate(chunks, 1):
        title = c.get("page_title") or "Untitled Page"
        url = c.get("source_url") or "Unknown URL"
        text = c.get("text", "").strip()
        context_blocks.append(
            f"[Source {idx}] (from: {title} — {url}):\n{text}"
        )

    return "\n\n".join(context_blocks)


def build_prompt(question: str, context: str) -> str:
    """Construct the final prompt containing system instructions, context, and query.

    Args:
        question: The user's query.
        context: The formatted context string.

    Returns:
        The prompt string.
    """
    return (
        "SYSTEM INSTRUCTIONS:\n"
        "You are WebGPT, a helpful assistant that answers questions based on content scraped from websites.\n\n"
        "RULES:\n"
        "1. Answer the user's question using ONLY the context provided below.\n"
        "2. If the context does not contain enough information to answer the question, respond with: "
        "\"I don't have enough information from the scraped content to answer this question.\"\n"
        "3. Do NOT make up information or use knowledge outside the provided context. If a fact cannot be found in the context, treat it as unknown.\n"
        "4. Answer naturally and use clean markdown formatting. Do NOT include any inline citations (such as [Source N], [N], or Source N) in your answer. Never mention source numbers or labels in the response body.\n"
        "5. Be concise but thorough. Use markdown formatting (bold, lists, code blocks) when appropriate.\n"
        "6. If multiple sources contain relevant information, synthesize them into a coherent answer.\n\n"
        f"--- CONTEXT ---\n\n{context}\n\n--- END CONTEXT ---\n\n"
        f"USER QUESTION:\n{question}"
    )


def extract_citations(
    chunks: list[dict[str, Any]],
    answer: str | None = None
) -> list[dict[str, str]]:
    """Identify which sources were cited in the answer and extract their metadata.

    If an answer is provided, scans the text for '[Source N]' references. If no
    explicit references are found, falls back to citing all retrieved chunks.
    Multiple chunks from the same page are deduplicated by URL.

    Args:
        chunks: The list of retrieved chunk dictionaries used for context.
        answer: The generated response text from the model.

    Returns:
        A list of citation dictionaries containing "source_url" and "page_title".
    """
    if not chunks:
        return []

    cited_indexes = set()
    if answer:
        # Regex to locate '[Source N]' markers in the generated text
        matches = re.findall(r"\[Source (\d+)\]", answer)
        for m in matches:
            try:
                # Convert 1-based source number to 0-based list index
                idx = int(m) - 1
                if 0 <= idx < len(chunks):
                    cited_indexes.add(idx)
            except ValueError:
                pass

    # Select cited chunks or default to all retrieved chunks if none were cited
    selected_chunks = [chunks[i] for i in sorted(cited_indexes)] if cited_indexes else chunks

    # Deduplicate by URL
    seen_urls = set()
    citations: list[dict[str, str]] = []
    for c in selected_chunks:
        url = c.get("source_url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            citations.append({
                "source_url": url,
                "page_title": c.get("page_title") or "Untitled Page"
            })

    return citations


def clean_citations_from_text(text: str) -> str:
    """Remove all inline source reference markers from the text response.

    Strips [Source N], [N], (Source N), and Source N (where N is a digit).
    """
    if not text:
        return text

    # Remove [Source \d+] or [Source \d]
    text = re.sub(r'\[Source\s+\d+\]', '', text, flags=re.IGNORECASE)
    # Remove (Source \d+) or (Source \d)
    text = re.sub(r'\(\s*Source\s+\d+\s*\)', '', text, flags=re.IGNORECASE)
    # Remove bracketed digits like [1], [2]
    text = re.sub(r'\[\s*\d+\s*\]', '', text)
    # Remove parenthesized digits like (1), (2)
    text = re.sub(r'\(\s*\d+\s*\)', '', text)
    # Remove standalone Source \d+ (e.g. "Source 1", "source 2")
    text = re.sub(r'\bSource\s+\d+\b', '', text, flags=re.IGNORECASE)

    # Clean up trailing spaces before punctuation or duplicate whitespace
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)
    # Clean up multiple spaces
    text = re.sub(r' +', ' ', text)
    # Clean up empty parentheses/brackets that might have been left
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'\[\s*\]', '', text)

    return text.strip()


async def generate_answer(job_id: Union[str, None], question: str) -> dict[str, Any]:
    """Execute the full RAG pipeline to answer a user's question.

    Steps:
    1. Input validation.
    2. Empty knowledge-base guard (vector store check, no embeddings).
    3. Context retrieval (embedding + vector search).
    4. Insufficient-context guard (grounded fallback, no LLM).
    5. Format context and build augmented prompt.
    6. Invoke the Multi-LLM Orchestration Service.
    7. Parse references in the answer and extract cited sources.

    Timing data for every phase is recorded and logged in a structured
    report at the end of the request (even on failure).

    Args:
        job_id: Scrape job UUID to search within, or None to search all.
        question: The user's natural language question.

    Returns:
        A dictionary with "answer" and "citations" lists.

    Raises:
        ValueError: If input is invalid.
        RuntimeError: If LLM service generation fails.
    """
    from app.services.llm_service import (
        generate_llm_answer,
        new_timing_data,
        rag_timing_context,
    )

    # Initialise per-request timing context
    timing = new_timing_data()
    token = rag_timing_context.set(timing)
    request_start = time.time()

    try:
        # 1. Input validation
        if not question or not question.strip():
            raise ValueError("Question cannot be empty or whitespace-only.")

        # 2. Empty knowledge-base guard — check vector store before embedding
        if not _has_any_indexed_content(job_id):
            logger.info("Empty knowledge base detected. Returning no-content response.")
            return {
                "answer": (
                    "No website has been indexed yet.\n\n"
                    "Please scrape a website first, then ask questions about its content."
                ),
                "citations": [],
            }

        # 3. Context Retrieval (embedding + vector search)
        retrieval_start = time.time()
        try:
            chunks = retrieve_context(job_id, question)
        except Exception as e:
            logger.error("RAG pipeline failed during context retrieval: %s", e)
            raise RuntimeError(f"Failed to retrieve context: {e}") from e
        timing["retrieval_time"] = round(time.time() - retrieval_start, 2)

        # 4. Insufficient-context guard — grounded fallback without invoking Gemini
        if not chunks:
            logger.info("No relevant chunks found for query. Returning grounded fallback response.")
            return {
                "answer": _build_insufficient_info_response(question, job_id),
                "citations": [],
            }

        # 5. Context & prompt construction
        prompt_start = time.time()
        context_str = build_context(chunks)
        timing["prompt_time"] = round(time.time() - prompt_start, 2)

        # 5. Multi-LLM provider API invocation
        logger.info("Invoking Multi-LLM Orchestration Service for question...")
        try:
            answer = await generate_llm_answer(context_str, question)
        except Exception as e:
            logger.exception("Multi-LLM answer generation failed: %s", e)
            raise RuntimeError(str(e)) from e

        # 6. Citation extraction and output formatting
        citations = extract_citations(chunks, answer)

        # 7. Post-process to remove all inline citation markers from response text
        clean_answer = clean_citations_from_text(answer)

        return {
            "answer": clean_answer,
            "citations": citations
        }

    finally:
        # Always log the structured timing report
        timing["total_time"] = round(time.time() - request_start, 2)
        _log_timing_report(timing)
        rag_timing_context.reset(token)


def _log_timing_report(timing: dict[str, Any]) -> None:
    """Print a structured performance report for a single RAG request."""
    lines = [
        "",
        f"Request ID: {timing['request_id']}",
        f"  Retrieval (embed + search): {timing['retrieval_time']}s",
        f"  Prompt Construction:        {timing['prompt_time']}s",
    ]
    for idx, attempt in enumerate(timing.get("attempts", []), 1):
        lines.append(
            f"  Attempt {idx}: {attempt['model']} -> {attempt['status']} ({attempt.get('elapsed', 0)}s)"
        )
    lines.append(f"  LLM Time:                   {timing.get('llm_time', 0)}s")
    lines.append(f"  Total Request:              {timing['total_time']}s")
    logger.info("\n".join(lines))
