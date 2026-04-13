from __future__ import annotations

import random
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright_stealth import Stealth


@asynccontextmanager
async def get_browser() -> AsyncGenerator[Browser, None]:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        try:
            yield browser
        finally:
            await browser.close()


@asynccontextmanager
async def get_page(browser: Browser) -> AsyncGenerator[Page, None]:
    context = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        locale="he-IL",
        timezone_id="Asia/Jerusalem",
        geolocation={"latitude": 32.08, "longitude": 34.78},
        permissions=["geolocation"],
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        extra_http_headers={
            "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )
    stealth = Stealth(
        navigator_languages_override=("he-IL", "he"),
        navigator_platform_override="MacIntel",
    )
    await stealth.apply_stealth_async(context)
    page = await context.new_page()
    try:
        yield page
    finally:
        await context.close()


async def load_page(page: Page, url: str, wait_selector: str | None = None) -> None:
    """Navigate to *url* and wait for content to be ready."""
    await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    await page.wait_for_timeout(random.randint(2000, 4000))

    # Simulate human-like scroll
    await page.evaluate("window.scrollBy(0, 300)")
    await page.wait_for_timeout(random.randint(500, 1000))

    if wait_selector:
        try:
            await page.wait_for_selector(wait_selector, timeout=10_000)
        except Exception:
            pass
