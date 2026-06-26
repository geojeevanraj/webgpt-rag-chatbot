"""Text embedding service using Google Gemini Embedding API.

Provides vector embedding generation using the Gemini API, completely removing
local SentenceTransformer dependencies to run efficiently in low-memory environments.
"""

import logging
import google.generativeai as genai
from typing import Any

from app.core.config import settings

# Configure module-level logger
logger = logging.getLogger(__name__)


def get_model() -> Any:
    """Retrieve embedding model (unused wrapper for backward compatibility)."""
    return None


def is_model_loaded() -> bool:
    """Check if the embedding model is loaded (always True for API-based)."""
    return True


def get_embedding_dimension() -> int:
    """Get the output vector dimension of the loaded embedding model.

    For models/gemini-embedding-001, this is 3072.
    """
    return 3072


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate vector embeddings for a list of text strings via Gemini API.

    Args:
        texts: A list of strings to embed.

    Returns:
        A list of float lists, where each list is a dense embedding vector.
        Returns an empty list if the input is empty.

    Raises:
        ValueError: If any text in the list is empty or whitespace-only.
        RuntimeError: If model inference fails.
    """
    if not texts:
        return []

    # Input validation: Ensure no empty or whitespace-only text is passed
    for i, t in enumerate(texts):
        if not t or not t.strip():
            raise ValueError(
                f"Validation failed: text at index {i} cannot be empty or whitespace-only."
            )

    logger.debug("Generating Gemini embeddings for batch of %d text segments", len(texts))
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        response = genai.embed_content(
            model=settings.EMBEDDING_MODEL,
            content=texts,
            task_type="retrieval_document"
        )
        embeddings = response.get("embedding", [])
        
        # Verify output alignment
        if len(embeddings) != len(texts):
            raise RuntimeError(
                f"Gemini API returned {len(embeddings)} embeddings for {len(texts)} inputs."
            )

        # Verify dimension
        expected_dim = get_embedding_dimension()
        for idx, vec in enumerate(embeddings):
            if len(vec) != expected_dim:
                raise RuntimeError(
                    f"Embedding dimension mismatch at index {idx}: "
                    f"expected {expected_dim}, got {len(vec)}."
                )

        return embeddings
    except Exception as e:
        logger.error("Failed to generate Gemini embeddings: %s", e)
        raise RuntimeError(f"Embedding generation failed: {e}") from e


def embed_text(text: str) -> list[float]:
    """Generate a vector embedding for a single text string.

    Args:
        text: The text string to embed.

    Returns:
        A list of floats representing the embedding vector.

    Raises:
        ValueError: If input validation fails (e.g. empty or whitespace-only text).
        RuntimeError: If model inference fails.
    """
    if not text or not text.strip():
        raise ValueError("Validation failed: input text cannot be empty or whitespace-only.")

    embeddings = embed_texts([text])
    return embeddings[0]
