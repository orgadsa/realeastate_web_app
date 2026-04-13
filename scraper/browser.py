from __future__ import annotations

import random
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright_stealth import Stealth

COOKIE_BUTTON_SELECTORS = [
    "button:has-text('אישור')",
    "button:has-text('אני מסכים')",
    "button:has-text('קיבלתי')",
    "button:has-text('אשר')",
    "button:has-text('Accept')",
    "button:has-text('OK')",
    "[class*='cookie'] button",
    "[class*='Cookie'] button",
    "[class*='consent'] button",
    "[class*='Consent'] button",
    "[id*='cookie'] button",
    "[id*='consent'] button",
]


@asynccontextmanager
async def get_browser() -> AsyncGenerator[Browser, None]:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )
        try:
            yield browser
        finally:
            await browser.close()


@asynccontextmanager
async def get_page(browser: Browser) -> AsyncGenerator[Page, None]:
    context = await browser.new_context(
        viewport={"width": 1366, "height": 768},
        locale="he-IL",
        timezone_id="Asia/Jerusalem",
        geolocation={"latitude": 32.08, "longitude": 34.78},
        permissions=["geolocation"],
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        ),
        extra_http_headers={
            "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "sec-ch-ua": '"Chromium";v="136", "Not.A/Brand";v="24", "Google Chrome";v="136"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
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


async def _dismiss_cookie_banner(page: Page) -> None:
    """Try to click cookie consent / accept buttons."""
    for sel in COOKIE_BUTTON_SELECTORS:
        try:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await btn.click()
                await page.wait_for_timeout(500)
                return
        except Exception:
            continue


async def load_page(page: Page, url: str, wait_selector: str | None = None) -> None:
    """Navigate to *url* and wait for content to be ready."""
    await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    await page.wait_for_timeout(random.randint(2000, 4000))

    await _dismiss_cookie_banner(page)

    # Simulate human-like scroll
    for offset in (300, 200, 400):
        await page.evaluate(f"window.scrollBy(0, {offset})")
        await page.wait_for_timeout(random.randint(300, 800))

    if wait_selector:
        try:
            await page.wait_for_selector(wait_selector, timeout=10_000)
        except Exception:
            pass
