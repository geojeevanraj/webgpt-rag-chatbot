"""Vector store service.

This module provides collection and document management in ChromaDB.
It implements a thread-safe singleton PersistentClient, handles batch chunk insertions
by dynamically calling the embedder service, validates vector sizes, checks heartbeat
health, and performs similarity searches using cosine distance.
"""

import logging
import threading
from typing import Any, Union

import chromadb
from chromadb.api.models.Collection import Collection

from app.core.config import settings
from app.services.embedder import embed_texts, get_embedding_dimension

# Configure module-level logger
logger = logging.getLogger(__name__)

# Module-level client instance and initialization lock
_client: Union[chromadb.PersistentClient, None] = None
_client_lock = threading.Lock()


def get_client() -> chromadb.PersistentClient:
    """Retrieve or initialize the ChromaDB PersistentClient singleton.

    This function is thread-safe and ensures that only one client instance is
    created, pointing to the database directory defined in configuration.

    Returns:
        The initialized ChromaDB PersistentClient instance.

    Raises:
        RuntimeError: If client initialization or heartbeat validation fails.
    """
    global _client

    if _client is not None:
        return _client

    with _client_lock:
        if _client is None:
            logger.info("Initializing ChromaDB PersistentClient at path: %s", settings.CHROMA_PERSIST_DIR)
            try:
                client_instance = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
                # Heartbeat check to validate connection
                heartbeat = client_instance.heartbeat()
                logger.info("ChromaDB PersistentClient connected successfully (heartbeat=%s)", heartbeat)
                _client = client_instance
            except Exception as e:
                logger.error("Failed to initialize ChromaDB PersistentClient: %s", e)
                raise RuntimeError(f"Vector store client initialization failed: {e}") from e

    return _client


def collection_exists(job_id: str) -> bool:
    """Check if a specific scrape job collection exists in ChromaDB.

    Args:
        job_id: The UUID of the scrape job.

    Returns:
        True if the collection exists, False otherwise.
    """
    client = get_client()
    collection_name = f"job_{job_id}"
    try:
        # Check by listing all collections (more robust across different API versions)
        collections = client.list_collections()
        names = []
        for col in collections:
            if isinstance(col, str):
                names.append(col)
            elif hasattr(col, "name"):
                names.append(col.name)

        if collection_name in names:
            return True

        # Fallback direct lookup
        client.get_collection(name=collection_name)
        return True
    except Exception:
        return False


def create_collection(job_id: str) -> Collection:
    """Create a new ChromaDB collection for a specific scrape job.

    Uses cosine distance metric as defined in the system architecture.
    If the collection already exists, returns the existing collection.

    Args:
        job_id: The UUID of the scrape job.

    Returns:
        The created or retrieved ChromaDB Collection instance.

    Raises:
        RuntimeError: If collection creation fails.
    """
    client = get_client()
    collection_name = f"job_{job_id}"
    logger.info("Creating ChromaDB collection: %s", collection_name)
    try:
        # Set distance metric to cosine via hnsw metadata settings
        return client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
    except Exception as e:
        logger.error("Failed to create collection %s: %s", collection_name, e)
        raise RuntimeError(f"Failed to create collection: {e}") from e


def get_collection(job_id: str) -> Collection:
    """Retrieve an existing ChromaDB collection for a scrape job.

    Args:
        job_id: The UUID of the scrape job.

    Returns:
        The retrieved ChromaDB Collection instance.

    Raises:
        ValueError: If the collection does not exist.
        RuntimeError: If retrieval fails due to database errors.
    """
    client = get_client()
    collection_name = f"job_{job_id}"
    try:
        return client.get_collection(name=collection_name)
    except Exception as e:
        # Handle missing collection explicitly as a ValueError for caller routing
        if "does not exist" in str(e) or not collection_exists(job_id):
            logger.warning("Requested collection %s does not exist", collection_name)
            raise ValueError(f"Collection for job {job_id} does not exist.") from e
        logger.error("Error retrieving collection %s: %s", collection_name, e)
        raise RuntimeError(f"Failed to retrieve collection: {e}") from e


def delete_collection(job_id: str) -> None:
    """Delete the ChromaDB collection associated with a scrape job.

    Does not raise an error if the collection does not exist.

    Args:
        job_id: The UUID of the scrape job to delete.

    Raises:
        RuntimeError: If deletion fails.
    """
    client = get_client()
    collection_name = f"job_{job_id}"
    logger.info("Deleting ChromaDB collection: %s", collection_name)
    try:
        if collection_exists(job_id):
            client.delete_collection(name=collection_name)
            logger.info("Successfully deleted collection: %s", collection_name)
        else:
            logger.info("Delete skipped: collection %s does not exist", collection_name)
    except Exception as e:
        logger.error("Failed to delete collection %s: %s", collection_name, e)
        raise RuntimeError(f"Failed to delete collection: {e}") from e


def get_collection_stats(job_id: str) -> dict[str, Any]:
    """Retrieve statistics for a specific scrape job collection.

    Args:
        job_id: The UUID of the scrape job.

    Returns:
        A dictionary containing collection statistics (e.g., "count").

    Raises:
        ValueError: If the collection does not exist.
    """
    collection = get_collection(job_id)
    try:
        count = collection.count()
        return {
            "collection_name": f"job_{job_id}",
            "count": count
        }
    except Exception as e:
        logger.error("Failed to read stats for collection job_%s: %s", job_id, e)
        raise RuntimeError(f"Failed to get collection stats: {e}") from e


def add_chunks(job_id: str, chunks: list[dict[str, Any]]) -> None:
    """Generate embeddings and upsert chunks into a scrape job collection.

    This function automatically generates text embeddings using the embedder service,
    packages the required metadata, and inserts them in safe batches into ChromaDB.
    Using `upsert` handles duplicate ID calls safely by updating the record.

    Args:
        job_id: The UUID of the scrape job.
        chunks: List of chunk dictionaries containing:
            "chunk_id", "source_url", "page_title", "chunk_index", and "text".

    Raises:
        ValueError: If the collection does not exist or input is invalid.
        RuntimeError: If embedding or insertion fails.
    """
    if not chunks:
        logger.info("[%s] No chunks provided to insert, skipping.", job_id)
        return

    collection = get_collection(job_id)
    expected_dim = get_embedding_dimension()

    # Extract text content for embedding generation
    texts = [c["text"] for c in chunks]

    # Generate embeddings in batch
    logger.info("[%s] Generating embeddings for %d chunks...", job_id, len(chunks))
    embeddings = embed_texts(texts)

    # Validate output dimension alignment
    if len(embeddings) != len(chunks):
        raise RuntimeError(
            f"Embedding length mismatch: generated {len(embeddings)} vectors for {len(chunks)} text items."
        )

    # Format items for ChromaDB insertion
    ids = [c["chunk_id"] for c in chunks]
    metadatas = [
        {
            "chunk_id": c["chunk_id"],
            "source_url": c["source_url"],
            "page_title": c["page_title"],
            "chunk_index": int(c["chunk_index"])
        }
        for c in chunks
    ]

    # SQLite parameters constraint: chunk size safety limit for ChromaDB batching (5000 items max)
    BATCH_SIZE = 5000
    total_chunks = len(chunks)

    logger.info("[%s] Inserting %d chunks into ChromaDB...", job_id, total_chunks)
    try:
        for idx in range(0, total_chunks, BATCH_SIZE):
            batch_end = min(idx + BATCH_SIZE, total_chunks)

            # Slice batches
            b_ids = ids[idx:batch_end]
            b_docs = texts[idx:batch_end]
            b_embeddings = embeddings[idx:batch_end]
            b_metadatas = metadatas[idx:batch_end]

            # double check dimension size of first vector in batch
            if b_embeddings and len(b_embeddings[0]) != expected_dim:
                raise ValueError(
                    f"Dimension mismatch check failed: expected {expected_dim}, got {len(b_embeddings[0])}."
                )

            # Use upsert to handle duplicate IDs gracefully (overwrites rather than crashes)
            collection.upsert(
                ids=b_ids,
                embeddings=b_embeddings,
                documents=b_docs,
                metadatas=b_metadatas
            )
        logger.info("[%s] Successfully indexed %d chunks.", job_id, total_chunks)
    except Exception as e:
        logger.error("[%s] Database insertion failed: %s", job_id, e)
        raise RuntimeError(f"ChromaDB upsert failed: {e}") from e


def similarity_search(
    job_id: str,
    query_embedding: list[float],
    top_k: int = 5
) -> list[dict[str, Any]]:
    """Retrieve top-K similar text chunks for a query vector.

    Args:
        job_id: The UUID of the collection to search.
        query_embedding: The query vector (must match embedding dimension, e.g., 384).
        top_k: Number of nearest neighbors to retrieve. Default: 5.

    Returns:
        A list of dictionaries representing the closest matching chunks:
            [{"chunk_id", "source_url", "page_title", "chunk_index", "text", "distance"}, ...]

    Raises:
        ValueError: If collection does not exist or dimension is invalid.
        RuntimeError: If query execution fails.
    """
    collection = get_collection(job_id)
    expected_dim = get_embedding_dimension()

    # Validate incoming query dimension
    if len(query_embedding) != expected_dim:
        raise ValueError(
            f"Query embedding dimension {len(query_embedding)} does not match model dimension {expected_dim}."
        )

    try:
        # Query ChromaDB (query_embeddings accepts a list of queries; we pass one)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )

        # Parse query output lists (ChromaDB structures them as list[list[Any]])
        retrieved_chunks: list[dict[str, Any]] = []

        # Check if any matches were returned
        if not results or not results.get("ids") or not results["ids"][0]:
            return []

        ids = results["ids"][0]
        documents = results["documents"][0] if results.get("documents") else []
        metadatas = results["metadatas"][0] if results.get("metadatas") else []
        distances = results["distances"][0] if results.get("distances") else []

        for i in range(len(ids)):
            meta = metadatas[i] if i < len(metadatas) else {}
            doc = documents[i] if i < len(documents) else ""
            dist = distances[i] if i < len(distances) else 2.0  # Cosine distance default max is 2.0

            retrieved_chunks.append({
                "chunk_id": meta.get("chunk_id", ids[i]),
                "source_url": meta.get("source_url", ""),
                "page_title": meta.get("page_title", ""),
                "chunk_index": int(meta.get("chunk_index", 0)),
                "text": doc,
                "distance": float(dist)
            })

        return retrieved_chunks
    except Exception as e:
        logger.error("Similarity search failed on job_%s: %s", job_id, e)
        raise RuntimeError(f"ChromaDB similarity search query failed: {e}") from e
