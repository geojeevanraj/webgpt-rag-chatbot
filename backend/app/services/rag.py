"""Retrieval-Augmented Generation (RAG) service.

This module orchestrates the RAG pipeline: embedding user questions, querying
the vector store, constructing prompts with retrieved contexts, invoking the
Gemini model, and extracting cited sources from the generated answers.
"""

import logging
import re
from typing import Any, Union

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from app.core.config import settings
from app.services.embedder import embed_text
from app.services.vector_store import (
    collection_exists,
    get_client,
    similarity_search,
)

# Configure module-level logger
logger = logging.getLogger(__name__)


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

    Args:
        job_id: The UUID of the scrape job, or None to search globally.
        question: The user's question.
        top_k: Max number of chunks to return. Default: 5.

    Returns:
        A list of matching chunk dictionaries sorted by distance (ascending).
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

    # Return top K items
    return filtered_chunks[:top_k]


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
        "4. Cite your sources using [Source N] format inline in your answer wherever you reference specific information.\n"
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


def generate_answer(job_id: Union[str, None], question: str) -> dict[str, Any]:
    """Execute the full RAG pipeline to answer a user's question.

    Steps:
    1. Embed query and search collection(s).
    2. Format context and build the augmented prompt.
    3. Invoke the Gemini API.
    4. Parse references in the answer and extract cited sources.

    Args:
        job_id: Scrape job UUID to search within, or None to search all.
        question: The user's natural language question.

    Returns:
        A dictionary with "answer" and "citations" lists.

    Raises:
        ValueError: If input is invalid.
        RuntimeError: If Gemini API or downstream queries fail.
    """
    # 1. Input validation
    if not question or not question.strip():
        raise ValueError("Question cannot be empty or whitespace-only.")

    # 2. Context Retrieval
    try:
        chunks = retrieve_context(job_id, question)
    except Exception as e:
        logger.error("RAG pipeline failed during context retrieval: %s", e)
        raise RuntimeError(f"Failed to retrieve context: {e}") from e

    # 3. Handle empty retrieval / insufficient context cases immediately
    fallback_msg = "I don't have enough information from the scraped content to answer this question."
    if not chunks:
        logger.info("No matching content found for query. Returning fallback response.")
        return {
            "answer": fallback_msg,
            "citations": []
        }

    # 4. Prompt construction
    context_str = build_context(chunks)
    prompt = build_prompt(question, context_str)

    # 5. Gemini API invocation
    logger.info("Configuring Gemini API client and invoking %s...", settings.GEMINI_MODEL)
    try:
        # Load API key and instantiate model client
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)

        # Restrict parameters for high factual grounding
        config = GenerationConfig(
            temperature=0.3,
            max_output_tokens=2048,
            top_p=0.95
        )

        start_time = time.time()
        response = model.generate_content(prompt, generation_config=config)
        elapsed = time.time() - start_time
        logger.info("Gemini inference completed in %.2f seconds", elapsed)

        answer = response.text
        if not answer:
            # Handle empty API response
            raise RuntimeError("Gemini returned an empty response text.")

    except Exception as e:
        # Map Gemini API exceptions cleanly
        logger.error("Gemini API invocation failed: %s", e)
        # Check if the error message is related to rate limiting (429)
        if "429" in str(e) or "quota" in str(e).lower():
            raise RuntimeError(
                "The AI service is temporarily busy. Please try again in a moment."
            ) from e
        raise RuntimeError(f"AI generation failed: {e}") from e

    # 6. Citation extraction and output formatting
    citations = extract_citations(chunks, answer)

    return {
        "answer": answer,
        "citations": citations
    }
