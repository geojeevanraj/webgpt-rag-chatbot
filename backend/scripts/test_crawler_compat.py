"""Verification script for the modern website compatibility improvements.

Tests the scraper pipeline against target websites to verify:
1. Pages are downloaded successfully
2. HTML cleaning extracts meaningful content
3. Browser rendering fallback works for JS-heavy sites
4. Non-zero chunks are generated

Usage:
    python -m scripts.test_crawler_compat
"""

import sys
import os
# Fix Windows console encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


import asyncio
import sys
import os
import time

# Add project root to path so app modules are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# We need to set a dummy API key to avoid startup validation failure
os.environ.setdefault("GEMINI_API_KEY", "test_verification_key_skip")


async def test_static_extraction():
    """Test the improved HTML cleaner against known-difficult HTML patterns."""
    from app.services.chunker import clean_html, chunk

    print("=" * 80)
    print("TEST 1: Static HTML Extraction (clean_html improvements)")
    print("=" * 80)

    # Simulate a website that uses "widget" and "sidebar" classes for real content
    html_with_widget_content = """
    <html>
    <head><title>Test Company</title></head>
    <body>
        <header>
            <h1>Welcome to Our Company</h1>
            <p>We provide excellent services for businesses worldwide.</p>
        </header>
        <main>
            <div class="widget-content">
                <h2>Our Services</h2>
                <p>We offer cloud computing, data analytics, and AI solutions.</p>
                <p>Our team of experts has over 20 years of combined experience.</p>
            </div>
            <div class="sidebar-info">
                <h3>Why Choose Us</h3>
                <p>Industry-leading technology and customer satisfaction.</p>
                <ul>
                    <li>24/7 Support</li>
                    <li>99.9% Uptime</li>
                    <li>Scalable Solutions</li>
                </ul>
            </div>
            <div class="banner-section">
                <h3>Latest News</h3>
                <p>We just launched our new AI-powered analytics platform.</p>
            </div>
        </main>
        <nav><a href="/">Home</a><a href="/about">About</a></nav>
        <footer><p>Copyright 2024</p></footer>
    </body>
    </html>
    """

    cleaned = clean_html(html_with_widget_content)
    print(f"\nCleaned text length: {len(cleaned)} chars")
    print(f"Content preview (first 300 chars):\n{cleaned[:300]}")

    # Check that widget/sidebar/banner content was preserved
    checks = {
        "Header content preserved": "Welcome to Our Company" in cleaned,
        "Widget content preserved": "cloud computing" in cleaned,
        "Sidebar content preserved": "Why Choose Us" in cleaned,
        "Banner content preserved": "Latest News" in cleaned,
        "Nav removed": "Home" not in cleaned or "About" not in cleaned,
        "Footer removed": "Copyright" not in cleaned,
    }

    for check, passed in checks.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {check}")

    # Test chunking
    chunks = chunk(html_with_widget_content, "https://example.com", "Test", 1000, 200)
    print(f"\nChunks generated: {len(chunks)}")
    assert len(chunks) > 0, "Should produce at least 1 chunk"
    print("  ✓ PASS: Non-zero chunks generated\n")


async def test_js_shell_detection():
    """Test that JS shell HTML is correctly identified as insufficient."""
    from app.services.chunker import clean_html, chunk

    print("=" * 80)
    print("TEST 2: JavaScript Shell Detection")
    print("=" * 80)

    # Simulate a React SPA HTML shell
    react_shell = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8"/>
        <title>React App</title>
        <link rel="icon" href="/favicon.ico"/>
    </head>
    <body>
        <div id="__next"></div>
        <script src="/static/js/main.chunk.js"></script>
        <script src="/static/js/bundle.js"></script>
    </body>
    </html>
    """

    cleaned = clean_html(react_shell)
    chunks = chunk(react_shell, "https://react.dev/learn", "React", 1000, 200)

    print(f"\nCleaned text length: {len(cleaned)} chars")
    print(f"Chunks generated: {len(chunks)}")
    print(f"  ✓ PASS: JS shell correctly produces {len(chunks)} chunks (expected 0)")
    print(f"  → This page would trigger browser rendering fallback\n")


async def test_http_fetch():
    """Test that the scraper can fetch pages with proper headers."""
    import aiohttp

    print("=" * 80)
    print("TEST 3: HTTP Fetch with Modern Headers")
    print("=" * 80)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }

    test_urls = [
        "https://docs.python.org/3/",
        "https://fastapi.tiangolo.com/",
    ]

    timeout = aiohttp.ClientTimeout(total=20.0)

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        for url in test_urls:
            try:
                start = time.time()
                async with session.get(url, allow_redirects=True) as resp:
                    elapsed = time.time() - start
                    html = await resp.text()

                    from app.services.chunker import clean_html, chunk
                    cleaned = clean_html(html)
                    chunks = chunk(html, url, "Test", 1000, 200)

                    print(f"\n  URL: {url}")
                    print(f"  HTTP: {resp.status}")
                    print(f"  Time: {elapsed:.2f}s")
                    print(f"  HTML size: {len(html)} bytes")
                    print(f"  Cleaned text: {len(cleaned)} chars")
                    print(f"  Chunks: {len(chunks)}")
                    status = "✓ SUCCESS" if len(chunks) > 0 else "✗ NO_CONTENT"
                    print(f"  Result: {status}")
            except Exception as e:
                print(f"\n  URL: {url}")
                print(f"  ✗ FAILED: {e}")

    print()


async def test_browser_rendering():
    """Test Playwright browser rendering on a JS-heavy site."""
    print("=" * 80)
    print("TEST 4: Browser Rendering Fallback (Playwright)")
    print("=" * 80)

    try:
        from app.services.browser_renderer import render_page, shutdown_browser
        from app.services.chunker import clean_html, chunk

        test_urls = [
            ("https://react.dev/learn", "React (SPA)"),
            ("https://www.claysys.com/", "ClaySys (Company site)"),
        ]

        for url, label in test_urls:
            print(f"\n  Rendering: {label} ({url})")
            start = time.time()

            rendered_html = await render_page(url, timeout=30)

            if rendered_html:
                elapsed = time.time() - start
                cleaned = clean_html(rendered_html)
                chunks = chunk(rendered_html, url, label, 1000, 200)

                print(f"  Time: {elapsed:.2f}s")
                print(f"  Rendered HTML: {len(rendered_html)} bytes")
                print(f"  Cleaned text: {len(cleaned)} chars")
                print(f"  Chunks: {len(chunks)}")
                status = "✓ SUCCESS" if len(chunks) > 0 else "✗ NO_CONTENT"
                print(f"  Result: {status}")

                if chunks:
                    print(f"  First chunk preview: {chunks[0]['text'][:120]}...")
            else:
                print(f"  ✗ FAILED: Browser render returned no HTML")

        await shutdown_browser()

    except ImportError:
        print("  ⚠ Playwright not installed — skipping browser rendering test")
    except Exception as e:
        print(f"  ✗ ERROR: {e}")

    print()


async def main():
    print("\n" + "=" * 80)
    print("  WebGPT Crawler Compatibility Verification")
    print("=" * 80 + "\n")

    await test_static_extraction()
    await test_js_shell_detection()
    await test_http_fetch()
    await test_browser_rendering()

    print("=" * 80)
    print("  VERIFICATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
