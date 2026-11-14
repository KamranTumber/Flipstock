"""Shared headless Chromium (Playwright) for pages that need a real browser."""

from __future__ import annotations

import asyncio
import logging
import random

from ..config import get_settings
from .base import BrowserUnavailable, LoginRequired, ScraperBlocked, looks_blocked, random_ua

log = logging.getLogger(__name__)


class BrowserPool:
    def __init__(self) -> None:
        self._pw = None
        self._browser = None
        self._lock = asyncio.Lock()
        self._sem = asyncio.Semaphore(2)  # max concurrent pages

    async def _ensure(self):
        async with self._lock:
            if self._browser is not None:
                return self._browser
            try:
                from playwright.async_api import async_playwright
            except ImportError as e:  # pragma: no cover
                raise BrowserUnavailable("Playwright is not installed (pip install playwright)") from e
            try:
                self._pw = await async_playwright().start()
                self._browser = await self._pw.chromium.launch(headless=get_settings().playwright_headless)
            except Exception as e:
                await self._safe_stop()
                raise BrowserUnavailable(
                    "Chromium for Playwright is not installed — run: python -m playwright install chromium"
                ) from e
            return self._browser

    async def _safe_stop(self):
        try:
            if self._browser:
                await self._browser.close()
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass
        self._browser = None
        self._pw = None

    async def close(self) -> None:
        async with self._lock:
            await self._safe_stop()

    async def render(
        self,
        url: str,
        *,
        wait_selector: str | None = None,
        cookies: list[dict] | None = None,
        block_markers: tuple[str, ...] = (),
        login_markers: tuple[str, ...] = (),
        scroll: int = 0,
        timeout_ms: int = 30000,
    ) -> str:
        browser = await self._ensure()
        async with self._sem:
            ctx = await browser.new_context(
                user_agent=random_ua(),
                locale="en-GB",
                timezone_id="Europe/London",
                viewport={"width": 1366, "height": 900},
            )
            try:
                if cookies:
                    await ctx.add_cookies(cookies)
                page = await ctx.new_page()
                await page.route(
                    "**/*",
                    lambda route: route.abort()
                    if route.request.resource_type in ("media", "font")
                    else route.continue_(),
                )
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                if wait_selector:
                    try:
                        await page.wait_for_selector(wait_selector, timeout=12000)
                    except Exception:
                        pass
                for _ in range(scroll):
                    await page.mouse.wheel(0, random.randint(1800, 2600))
                    await page.wait_for_timeout(random.randint(700, 1200))
                html = await page.content()
                final_url = page.url
            finally:
                await ctx.close()

        status = resp.status if resp else 0
        low = html[:40000].lower()
        if any(m in final_url for m in ("/login", "checkpoint")) or any(m in low for m in login_markers):
            raise LoginRequired("login wall")
        marker = looks_blocked(html, block_markers)
        if marker:
            raise ScraperBlocked(f"anti-bot page in browser ('{marker}')")
        if status in (403, 429):
            raise ScraperBlocked(f"HTTP {status} in browser")
        return html


browser_pool = BrowserPool()
