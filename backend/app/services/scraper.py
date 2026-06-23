"""Asynchronous BFS Web Scraper Service.

This module provides the core web crawling capability for the WebGPT application.
It implements a Breadth-First Search (BFS) crawler using aiohttp for async HTTP
requests and BeautifulSoup for HTML parsing. It respects robots.txt, limits
crawling to the seed domain, enforces depth and page limits, filters out binary
files, and implements polite crawling delays.
"""

import asyncio
from collections import deque
import logging
from typing import Any, Callable, Coroutine, Union
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import aiohttp
from bs4 import BeautifulSoup

from app.core.config import settings

# Configure module-level logger
logger = logging.getLogger(__name__)

# Standard set of binary/non-content file extensions to skip during link discovery
BINARY_EXTENSIONS: set[str] = {
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".zip", ".tar", ".gz", ".exe", ".dmg", ".mp3", ".mp4", ".avi",
    ".css", ".js", ".json", ".xml", ".woff", ".woff2", ".ttf", ".eot"
}


def normalize_url(url: str) -> str:
    """Normalize a URL to prevent duplicate scraping of identical pages.

    Normalization steps:
    1. Lowercase the scheme and hostname.
    2. Strip fragment identifiers (e.g., #section).
    3. Strip trailing slashes from the path.
    4. Sort query parameters alphabetically to treat differently ordered queries
       as the same page.

    Args:
        url: The raw URL string.

    Returns:
        The normalized URL string.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Clean path (strip trailing slashes, but preserve a single root slash)
    path = parsed.path
    if path and path != "/":
        path = path.rstrip("/")

    # Parse, sort, and re-serialize query parameters to handle different orders
    query = parsed.query
    if query:
        params = parse_qsl(query, keep_blank_values=True)
        params.sort()
        query = urlencode(params)

    # Reconstruct the URL without fragments
    normalized_parts = (scheme, netloc, path, parsed.params, query, "")
    return urlunparse(normalized_parts)


def is_same_domain(url: str, seed_host: str) -> bool:
    """Verify if a URL belongs to the exact same host/domain as the seed URL.

    Args:
        url: The URL to check.
        seed_host: The host/domain of the seed URL (e.g., 'docs.example.com').

    Returns:
        True if the URL host matches the seed host, False otherwise.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return False
    return hostname.lower() == seed_host.lower()


def is_binary_extension(url: str) -> bool:
    """Check if the URL path ends with a known binary or asset file extension.

    Args:
        url: The URL to check.

    Returns:
        True if the URL points to a binary/asset extension, False otherwise.
    """
    parsed = urlparse(url)
    path = parsed.path.lower()
    return any(path.endswith(ext) for ext in BINARY_EXTENSIONS)


def extract_title(html: str) -> str:
    """Extract the <title> tag text content from raw HTML.

    Args:
        html: Raw HTML content.

    Returns:
        The text content of the title tag, or an empty string if not found.
    """
    soup = BeautifulSoup(html, "lxml")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return ""


def extract_links(html: str, base_url: str) -> list[str]:
    """Extract all valid hyperlinks from HTML content and resolve them against a base URL.

    Args:
        html: Raw HTML content.
        base_url: The current page URL, used to resolve relative hrefs.

    Returns:
        A list of resolved absolute URLs.
    """
    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        # Skip internal protocol links
        if href.lower().startswith(("javascript:", "mailto:", "tel:")):
            continue
        resolved = urljoin(base_url, href)
        links.append(resolved)
    return links


async def fetch_robots_txt(
    session: aiohttp.ClientSession, seed_url: str
) -> RobotFileParser:
    """Asynchronously fetch and parse robots.txt for the domain of the seed URL.

    If robots.txt is missing (e.g., 404), unreachable, or fails to parse, a
    permissive parser is returned which allows crawling all paths by default.

    Args:
        session: Active aiohttp ClientSession.
        seed_url: The seed URL to extract the domain from.

    Returns:
        A RobotFileParser instance representing the domain's robots.txt rules.
    """
    parsed = urlparse(seed_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()

    logger.info("Fetching robots.txt from %s", robots_url)
    try:
        # Set a short 5.0 second timeout for robots.txt fetching to avoid blocking the crawler
        timeout = aiohttp.ClientTimeout(total=5.0)
        async with session.get(robots_url, timeout=timeout) as response:
            if response.status == 200:
                content = await response.text()
                rp.parse(content.splitlines())
                logger.info("Successfully parsed robots.txt from %s", robots_url)
            else:
                logger.info(
                    "robots.txt returned status %d for %s; assuming permissive access",
                    response.status,
                    robots_url
                )
                rp.parse([])
    except Exception as e:
        logger.warning(
            "Failed to fetch robots.txt from %s: %s. Assuming permissive access.",
            robots_url,
            e
        )
        rp.parse([])

    return rp


async def scrape(
    seed_url: str,
    max_depth: int,
    max_pages: int,
    job_id: str,
    on_page_scraped: Callable[
        [str, str, str, int, str, Union[str, None]],
        Union[Coroutine[Any, Any, None], Any]
    ],
) -> dict[str, int]:
    """Recursively crawls a website starting from a seed URL using Breadth-First Search (BFS).

    This function is run asynchronously. It processes discovered pages sequentially,
    enforcing polite delays between requests. Results for each page (success or failure)
    are sent back to the caller in real-time via the `on_page_scraped` callback.

    Args:
        seed_url: The starting URL for the crawl.
        max_depth: Maximum recursion depth from the seed URL (typically 1 to 3).
        max_pages: Maximum number of successfully scraped pages allowed (1 to 100).
        job_id: The UUID of the scraping job (used for logging context).
        on_page_scraped: Callback function triggered after each page processing attempt.
            Signature: (url, title, raw_html, depth, status, error_message).

    Returns:
        A summary dictionary containing:
            - "total_pages_attempted": Total unique pages requested (success or failure)
            - "total_pages_scraped": Count of successfully scraped HTML pages
            - "total_pages_failed": Count of pages that encountered request/processing errors
    """
    parsed_seed = urlparse(seed_url)
    seed_host = parsed_seed.hostname or ""
    if not seed_host:
        logger.error("[%s] Invalid seed URL hostname for: %s", job_id, seed_url)
        return {"total_pages_attempted": 0, "total_pages_scraped": 0, "total_pages_failed": 0}

    # Queue contains tuples of (url, current_depth)
    queue: deque[tuple[str, int]] = deque([(seed_url, 0)])
    visited: set[str] = set()

    pages_scraped = 0
    pages_failed = 0

    # Configure aiohttp connection limits and timeouts based on core settings
    timeout = aiohttp.ClientTimeout(
        total=float(settings.SCRAPE_TIMEOUT_SECONDS),
        connect=5.0
    )

    logger.info(
        "[%s] Starting crawl for %s (max_depth=%d, max_pages=%d)",
        job_id, seed_url, max_depth, max_pages
    )

    async with aiohttp.ClientSession(timeout=timeout) as session:
        # Fetch robots.txt first to respect crawling policies
        robot_parser = await fetch_robots_txt(session, seed_url)

        while queue and pages_scraped < max_pages:
            current_url, depth = queue.popleft()
            normalized_url = normalize_url(current_url)

            # Skip already visited pages
            if normalized_url in visited:
                continue
            visited.add(normalized_url)

            # Enforce robots.txt rules
            if not robot_parser.can_fetch("*", current_url):
                logger.info("[%s] Skipping %s: disallowed by robots.txt", job_id, current_url)
                continue

            network_fetch_attempted = False
            logger.info("[%s] Fetching page: %s (depth=%d)", job_id, current_url, depth)

            try:
                network_fetch_attempted = True
                async with session.get(current_url, allow_redirects=True, max_redirects=3) as response:
                    # Enforce HTTP errors (4xx/5xx raise ClientResponseError if we call raise_for_status)
                    # We handle them explicitly to capture custom error messages
                    if response.status >= 400:
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status,
                            message=f"HTTP Error {response.status}",
                            headers=response.headers
                        )

                    # Only accept HTML content type
                    content_type = response.headers.get("Content-Type", "").lower()
                    if "text/html" not in content_type:
                        logger.info(
                            "[%s] Skipping content-type %s for %s",
                            job_id, content_type, current_url
                        )
                        # Remove from attempt counts since we skip it silently
                        network_fetch_attempted = False
                        continue

                    # Check Content-Length header first if available to save bandwidth
                    content_length = response.headers.get("Content-Length")
                    if content_length:
                        try:
                            if int(content_length) > 5 * 1024 * 1024:
                                logger.warning(
                                    "[%s] Skipping large page %s (Content-Length: %s bytes)",
                                    job_id, current_url, content_length
                                )
                                network_fetch_attempted = False
                                continue
                        except ValueError:
                            pass

                    # Read payload in chunks to enforce a hard 5MB memory limit protection
                    content_chunks: list[bytes] = []
                    total_bytes = 0
                    while True:
                        chunk = await response.content.read(64 * 1024)  # Read 64KB
                        if not chunk:
                            break
                        total_bytes += len(chunk)
                        if total_bytes > 5 * 1024 * 1024:
                            raise ValueError("Response payload size exceeded 5MB limit")
                        content_chunks.append(chunk)

                    body_bytes = b"".join(content_chunks)
                    raw_html = body_bytes.decode(response.charset or "utf-8", errors="replace")

                    # Successfully scraped: extract title and trigger callback
                    title = extract_title(raw_html)
                    pages_scraped += 1

                    callback_res = on_page_scraped(
                        current_url, title, raw_html, depth, "scraped", None
                    )
                    if asyncio.iscoroutine(callback_res):
                        await callback_res

                    # Discover and queue internal links if we haven't reached max depth
                    if depth < max_depth:
                        links = extract_links(raw_html, current_url)
                        for link in links:
                            normalized_link = normalize_url(link)
                            if (
                                is_same_domain(normalized_link, seed_host)
                                and normalized_link not in visited
                                and not is_binary_extension(normalized_link)
                            ):
                                queue.append((link, depth + 1))

            except Exception as e:
                logger.error("[%s] Error scraping %s: %s", job_id, current_url, e)
                pages_failed += 1
                try:
                    callback_res = on_page_scraped(
                        current_url, "", "", depth, "failed", str(e)
                    )
                    if asyncio.iscoroutine(callback_res):
                        await callback_res
                except Exception as callback_err:
                    logger.exception(
                        "[%s] Error running callback for failed scrape on %s: %s",
                        job_id, current_url, callback_err
                    )

            # Apply polite crawl delay if a network request was made and the queue still has items
            if network_fetch_attempted and queue and pages_scraped < max_pages:
                await asyncio.sleep(settings.SCRAPE_DELAY_SECONDS)

    logger.info(
        "[%s] Crawl complete. Scraped=%d, Failed=%d, Left in queue=%d",
        job_id, pages_scraped, pages_failed, len(queue)
    )

    return {
        "total_pages_attempted": pages_scraped + pages_failed,
        "total_pages_scraped": pages_scraped,
        "total_pages_failed": pages_failed,
    }
