"""Browser rendering fallback using Playwright.

This module provides headless Chromium rendering for JavaScript-heavy websites
that return empty HTML shells when fetched via plain HTTP requests (e.g., React
SPAs, Next.js CSR pages). It is used as a fallback when static HTML extraction
produces insufficient content.

Design:
- Lazy singleton: The browser instance is only launched on first use.
- Graceful degradation: If Playwright is not installed or browser binaries are
  missing, the module returns None and logs a warning — it never crashes the
  scraping pipeline.
- Auto-cleanup: Pages are closed after extraction to prevent memory leaks.
"""

import asyncio
import logging
from typing import Union

logger = logging.getLogger(__name__)

# Module-level singleton browser instance
_browser = None
_browser_lock = asyncio.Lock()
_playwright_instance = None
_playwright_available: Union[bool, None] = None  # None = not yet checked


async def _check_playwright_available() -> bool:
    """Check if Playwright is installed and browser binaries are available."""
    global _playwright_available
    if _playwright_available is not None:
        return _playwright_available

    try:
        import playwright  # noqa: F401
        _playwright_available = True
        return True
    except ImportError:
        logger.warning(
            "Playwright is not installed. Browser rendering fallback is disabled. "
            "Install with: pip install playwright && playwright install chromium"
        )
        _playwright_available = False
        return False


async def _get_browser():
    """Get or create the singleton Playwright browser instance.

    Returns:
        A Playwright Browser instance, or None if Playwright is unavailable.
    """
    global _browser, _playwright_instance

    if not await _check_playwright_available():
        return None

    # Fast path: browser already running
    if _browser is not None and _browser.is_connected():
        return _browser

    async with _browser_lock:
        # Double-check after acquiring lock
        if _browser is not None and _browser.is_connected():
            return _browser

        try:
            from playwright.async_api import async_playwright

            logger.info("Launching Playwright headless Chromium browser...")
            _playwright_instance = await async_playwright().start()
            _browser = await _playwright_instance.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-extensions",
                ]
            )
            logger.info("Playwright browser launched successfully.")
            return _browser
        except Exception as e:
            logger.error(
                "Failed to launch Playwright browser: %s. "
                "Browser rendering fallback is disabled for this session. "
                "Ensure browser binaries are installed: playwright install chromium",
                e,
            )
            _playwright_available = False
            return None


async def render_page(url: str, timeout: int = 30) -> Union[str, None]:
    """Render a page in headless Chromium and return the fully rendered HTML.

    Uses Playwright to navigate to the URL, waits for the page to reach
    network idle state (no pending network requests for 500ms), then
    extracts the rendered DOM.

    Args:
        url: The URL to render.
        timeout: Maximum time in seconds to wait for the page to load.

    Returns:
        The rendered HTML string, or None if rendering fails or Playwright
        is unavailable.
    """
    browser = await _get_browser()
    if browser is None:
        return None

    page = None
    try:
        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
        )

        logger.info("Browser rendering: navigating to %s (timeout=%ds)", url, timeout)

        # Navigate and wait for network idle (no pending requests for 500ms)
        try:
            await page.goto(
                url,
                wait_until="networkidle",
                timeout=timeout * 1000,  # Playwright uses milliseconds
            )
            # Additional short wait for any late-firing JS (e.g., hydration)
            await asyncio.sleep(1.0)
        except Exception as goto_err:
            # Handle TimeoutError gracefully by attempting to extract content anyway.
            # Many websites have analytics or tracking pixels that prevent absolute networkidle.
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            if isinstance(goto_err, PlaywrightTimeoutError) or "timeout" in str(goto_err).lower():
                logger.warning(
                    "Timeout waiting for networkidle on %s: %s. Attempting to extract currently loaded DOM.",
                    url,
                    goto_err,
                )
            else:
                raise goto_err

        # Extract the fully rendered DOM
        rendered_html = await page.content()

        logger.info(
            "Browser rendering complete for %s (rendered HTML: %d bytes)",
            url,
            len(rendered_html),
        )
        return rendered_html

    except Exception as e:
        logger.warning("Browser rendering failed for %s: %s", url, e)
        return None

    finally:
        if page is not None:
            try:
                await page.close()
            except Exception:
                pass


async def shutdown_browser() -> None:
    """Gracefully shut down the Playwright browser instance.

    Safe to call even if the browser was never started.
    """
    global _browser, _playwright_instance

    if _browser is not None:
        try:
            await _browser.close()
            logger.info("Playwright browser closed.")
        except Exception as e:
            logger.warning("Error closing Playwright browser: %s", e)
        _browser = None

    if _playwright_instance is not None:
        try:
            await _playwright_instance.stop()
        except Exception:
            pass
        _playwright_instance = None

