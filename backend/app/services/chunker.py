"""HTML cleaning and text chunking service.

This module provides text extraction and chunking services. It parses raw HTML,
removes boilerplate content (navigation, headers, footers, etc.), cleans the
remaining text, and splits it recursively into overlapping, size-bounded chunks
suitable for vector database embeddings.
"""

import hashlib
import logging
import re
from typing import Any
import uuid
from bs4 import BeautifulSoup

# Configure module-level logger
logger = logging.getLogger(__name__)

# Standard set of binary/non-content file extensions or assets to ignore
# (if any leak into raw html processing, though typically handled by scraper)
BOILERPLATE_PATTERNS: list[str] = [
    "nav", "navbar", "footer", "sidebar", "menu", "cookie",
    "banner", "ad", "advertisement", "popup", "modal", "widget",
    "social", "share", "header"
]


def clean_html(html_content: str) -> str:
    """Parse raw HTML, remove semantic boilerplate and metadata, and extract clean text.

    Boilerplate removed includes scripts, styles, iframes, SVGs, nav, headers, footers,
    and elements with matching classes/IDs (like sidebars, ads, popups).
    If a <main> or <article> tag is present, text is extracted only from it.

    Args:
        html_content: The raw HTML string.

    Returns:
        The cleaned text extracted from the HTML.
    """
    # lxml parser is fast and lenient with malformed HTML
    soup = BeautifulSoup(html_content, "lxml")

    # 1. Decompose entirely useless semantic tags
    unwanted_tags = ["script", "style", "noscript", "iframe", "svg", "nav", "footer", "header"]
    for tag in soup.find_all(unwanted_tags):
        tag.decompose()

    # 2. Decompose common boilerplate elements by class and ID
    def is_boilerplate(tag: Any) -> bool:
        # Check ID attribute
        tag_id = tag.get("id")
        if tag_id and any(pattern in tag_id.lower() for pattern in BOILERPLATE_PATTERNS):
            return True

        # Check Class attribute (can be a list of strings or a single string)
        tag_classes = tag.get("class")
        if tag_classes:
            if isinstance(tag_classes, list):
                for cls in tag_classes:
                    if any(pattern in cls.lower() for pattern in BOILERPLATE_PATTERNS):
                        return True
            elif isinstance(tag_classes, str):
                if any(pattern in tag_classes.lower() for pattern in BOILERPLATE_PATTERNS):
                    return True
        return False

    for tag in soup.find_all(is_boilerplate):
        tag.decompose()

    # 3. Extract text from primary content tags, falling back to body or html root
    content_tag = soup.find("main") or soup.find("article") or soup.find("body") or soup
    text = content_tag.get_text(separator="\n", strip=True)

    # 4. Clean formatting and whitespace
    # Collapse 3 or more newlines into exactly 2 (preserves paragraph breaks)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse multiple consecutive spaces into a single space
    text = re.sub(r" {2,}", " ", text)
    # Strip leading/trailing whitespace
    return text.strip()


def split_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]:
    """Recursively splits text into smaller segments that fit within chunk_size.

    Maintains overlapping characters between consecutive chunks and attempts to split
    along semantic boundaries (paragraphs, sentences, words) to preserve coherence.

    Args:
        text: The clean input text.
        chunk_size: Maximum character length of each chunk.
        chunk_overlap: Number of characters to overlap between consecutive chunks.

    Returns:
        A list of split text chunks.
    """
    if len(text) <= chunk_size:
        return [text]

    # Pre-defined hierarchy of separators for semantic splits
    separators = ["\n\n", "\n", ". ", " ", ""]
    separator = ""
    for sep in separators:
        if sep in text:
            separator = sep
            break

    # Split the text by the chosen separator
    if separator == "":
        splits = list(text)
    else:
        splits = text.split(separator)

    chunks: list[str] = []
    current_doc: list[str] = []
    current_len = 0

    for s in splits:
        # If a single item exceeds the chunk size limit, split it recursively
        if len(s) > chunk_size:
            # Flush any accumulated content first
            if current_doc:
                chunks.append(separator.join(current_doc))
                current_doc = []
                current_len = 0

            # Recurse on the large split item
            sub_chunks = split_text(s, chunk_size, chunk_overlap)
            chunks.extend(sub_chunks)
            continue

        # Calculate the length of the new candidate chunk
        add_len = len(s) + (len(separator) if current_doc else 0)

        if current_len + add_len <= chunk_size:
            current_doc.append(s)
            current_len += add_len
        else:
            # Yield the current accumulated chunk
            if current_doc:
                chunks.append(separator.join(current_doc))

            # Maintain semantic overlaps: pop elements from the start of the
            # queue until the accumulated size is <= chunk_overlap.
            # This ensures subsequent chunks start with elements from the end of the previous chunk.
            while current_doc and current_len > chunk_overlap:
                removed = current_doc.pop(0)
                current_len -= (len(removed) + len(separator))

            current_doc.append(s)
            current_len += len(s) + (len(separator) if current_doc else 0)

    # Append any remaining content
    if current_doc:
        chunks.append(separator.join(current_doc))

    return chunks


def chunk(
    raw_html: str,
    source_url: str,
    page_title: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[dict[str, Any]]:
    """Clean HTML content and slice it into structured overlapping chunks.

    Args:
        raw_html: Raw page HTML.
        source_url: The URL of the page being chunked.
        page_title: The title of the page.
        chunk_size: Maximum character length per chunk.
        chunk_overlap: Number of characters to overlap between consecutive chunks.

    Returns:
        A list of chunk dicts ready for ChromaDB indexing, each containing:
            - "chunk_id": A unique, deterministic UUID5 generated from URL & index.
            - "source_url": The source URL.
            - "page_title": The page title.
            - "chunk_index": The index of the chunk.
            - "text": The textual content of the chunk.
        Returns an empty list if the cleaned page contains fewer than 50 characters.
    """
    cleaned_text = clean_html(raw_html)

    # Ignore pages with insufficient content (e.g., error pages or empty shells)
    if len(cleaned_text) < 50:
        logger.info(
            "Page %s skipped for chunking: cleaned text length (%d) is under 50 characters.",
            source_url,
            len(cleaned_text)
        )
        return []

    split_chunks = split_text(cleaned_text, chunk_size, chunk_overlap)

    result_chunks: list[dict[str, Any]] = []
    seen_texts: set[str] = set()

    for idx, chunk_text in enumerate(split_chunks):
        # Handle exact duplicate chunks within the page (e.g., repeating inline text blocks)
        text_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
        if text_hash in seen_texts:
            logger.info("Skipping duplicate chunk on page %s at index %d", source_url, idx)
            continue
        seen_texts.add(text_hash)

        # Generate a deterministic UUID5 namespace id for ChromaDB indexing consistency
        chunk_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_url}/chunk_{idx}"))

        result_chunks.append({
            "chunk_id": chunk_uuid,
            "source_url": source_url,
            "page_title": page_title,
            "chunk_index": idx,
            "text": chunk_text
        })

    return result_chunks
