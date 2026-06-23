"""Text embedding service.

This module provides vector embedding generation using the SentenceTransformers
library. It implements a thread-safe singleton pattern to cache the model in memory,
ensuring fast reuse across requests. It supports lazy initialization, health
validations, single/batch embedding operations, and vector dimension verification.
"""

import logging
import threading
import time
from typing import Union
from sentence_transformers import SentenceTransformer

from app.core.config import settings

# Configure module-level logger
logger = logging.getLogger(__name__)

# Module-level model instance and initialization lock
_model: Union[SentenceTransformer, None] = None
_model_lock = threading.Lock()


def get_model() -> SentenceTransformer:
    """Retrieve or initialize the SentenceTransformer model singleton.

    This function is thread-safe and lazily loads the embedding model
    into memory, executing a health check before returning.

    Returns:
        The loaded SentenceTransformer model instance.

    Raises:
        RuntimeError: If the model fails to load or fails its health check.
    """
    global _model

    if _model is not None:
        return _model

    with _model_lock:
        # Double-checked locking pattern to prevent concurrent duplicate loads
        if _model is None:
            logger.info("Initializing embedding model singleton: %s", settings.EMBEDDING_MODEL)
            start_time = time.time()
            try:
                # Load SentenceTransformer model (will download and cache if not local)
                loaded_model = SentenceTransformer(settings.EMBEDDING_MODEL)

                # Health validation check: run a dummy encoding to ensure model is working
                test_val = loaded_model.encode(["health check"], normalize_embeddings=True)
                dim = int(loaded_model.get_sentence_embedding_dimension())
                if test_val.shape[1] != dim:
                    raise RuntimeError(
                        f"Health check failed: expected dimension {dim}, got {test_val.shape[1]}"
                    )

                _model = loaded_model
                elapsed = time.time() - start_time
                logger.info(
                    "Loaded and validated embedding model %s in %.2f seconds (dimension=%d)",
                    settings.EMBEDDING_MODEL,
                    elapsed,
                    dim
                )
            except Exception as e:
                logger.error(
                    "Failed to initialize embedding model %s: %s",
                    settings.EMBEDDING_MODEL,
                    e
                )
                raise RuntimeError(
                    f"Embedding model initialization failed: {e}"
                ) from e

    return _model


def is_model_loaded() -> bool:
    """Check if the embedding model is currently loaded in memory.

    Returns:
        True if the model singleton is loaded, False otherwise.
    """
    return _model is not None


def get_embedding_dimension() -> int:
    """Get the output vector dimension of the loaded embedding model.

    For all-MiniLM-L6-v2, this is 384.

    Returns:
        The integer dimension.

    Raises:
        RuntimeError: If the model fails to load.
    """
    model = get_model()
    return int(model.get_sentence_embedding_dimension())


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate vector embeddings for a list of text strings.

    Args:
        texts: A list of strings to embed.

    Returns:
        A list of float lists, where each list is a dense embedding vector.
        Returns an empty list if the input is empty.

    Raises:
        ValueError: If any text in the list is empty or whitespace-only.
        RuntimeError: If model inference fails or output dimension is incorrect.
    """
    if not texts:
        return []

    # Input validation: Ensure no empty or whitespace-only text is passed
    for i, t in enumerate(texts):
        if not t or not t.strip():
            raise ValueError(
                f"Validation failed: text at index {i} cannot be empty or whitespace-only."
            )

    model = get_model()
    expected_dim = get_embedding_dimension()

    logger.debug("Generating embeddings for batch of %d text segments", len(texts))
    try:
        # encode returns a numpy ndarray
        # normalize_embeddings=True ensures cosine similarity maps directly to dot product
        embeddings_ndarray = model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True
        )
        embeddings_list = embeddings_ndarray.tolist()

        # Output verification
        for idx, vec in enumerate(embeddings_list):
            if len(vec) != expected_dim:
                raise RuntimeError(
                    f"Embedding dimension mismatch at index {idx}: "
                    f"expected {expected_dim}, got {len(vec)}."
                )

        return embeddings_list  # type: ignore[no-any-return]
    except Exception as e:
        logger.error("Failed to generate embeddings: %s", e)
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
