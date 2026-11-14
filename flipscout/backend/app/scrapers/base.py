"""Shared HTTP plumbing: UA rotation, per-host rate limiting, retries, block detection."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import re
import time
from urllib.parse import urlparse

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


class ScraperError(Exception):
    """Generic scraper failure (network, parse)."""


class ScraperBlocked(ScraperError):
    """Anti-bot page, CAPTCHA, 403 or rate limit."""


class LoginRequired(ScraperError):
    """Source needs an authenticated session."""


class BrowserUnavailable(ScraperError):
    """Playwright / Chromium not installed or failed to start."""


def random_ua() -> str:
    return random.choice(USER_AGENTS)


def browser_headers(ua: str | None = None) -> dict[str, str]:
    return {
        "User-Agent": ua or random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Cache-Control": "no-cache",
        "Upgrade-Insecure-Requests": "1",
    }


class HostRateLimiter:
    """Ensures a minimum (jittered) interval between requests to the same host."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._last: dict[str, float] = {}

    async def wait(self, host: str, min_interval: float) -> None:
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            gap = min_interval * random.uniform(0.8, 1.4)
            delay = self._last.get(host, 0) + gap - now
            if delay > 0:
                await asyncio.sleep(delay)
            self._last[host] = time.monotonic()


rate_limiter = HostRateLimiter()

GENERIC_BLOCK_MARKERS = (
    "pardon our interruption",
    "verify you are a human",
    "verify you are human",
    "are you a robot",
    "captcha-delivery.com",
    "cf-chl-",
    "challenge-platform",
    "access denied",
    "request unsuccessful. incapsula",
)


def looks_blocked(text: str, extra_markers: tuple[str, ...] = ()) -> str | None:
    head = text[:20000].lower()
    for m in GENERIC_BLOCK_MARKERS + extra_markers:
        if m in head:
            return m
    return None


class Http:
    """Thin async HTTP wrapper shared by all scrapers in one search."""

    def __init__(self) -> None:
        cfg = get_settings()
        self.cfg = cfg
        self.client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=cfg.request_timeout,
            headers=browser_headers(),
        )

    async def aclose(self) -> None:
        await self.client.aclose()

    async def request(self, method: str, url: str, *, min_interval: float | None = None, **kw) -> httpx.Response:
        host = urlparse(url).netloc
        last_exc: Exception | None = None
        extra_headers = kw.pop("headers", None) or {}
        for attempt in range(self.cfg.max_retries + 1):
            await rate_limiter.wait(host, self.cfg.min_request_interval if min_interval is None else min_interval)
            headers = {**browser_headers(), **extra_headers}  # fresh UA each attempt
            try:
                r = await self.client.request(method, url, headers=headers, **kw)
            except httpx.TimeoutException as e:
                last_exc = e
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            except httpx.HTTPError as e:
                raise ScraperError(f"{host}: {e.__class__.__name__}") from e
            if r.status_code in (429, 503) and attempt < self.cfg.max_retries:
                retry_after = r.headers.get("retry-after")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else 2.0 * (attempt + 1) ** 2
                log.info("%s rate-limited (%s); retrying in %.1fs", host, r.status_code, wait)
                await asyncio.sleep(min(wait, 15))
                continue
            return r
        if last_exc:
            raise ScraperError(f"{host}: timed out") from last_exc
        raise ScraperBlocked(f"{host}: rate limited (HTTP 429/503)")

    async def get_html(self, url: str, *, block_markers: tuple[str, ...] = (), **kw) -> str:
        r = await self.request("GET", url, **kw)
        if r.status_code in (401, 403, 429, 503):
            raise ScraperBlocked(f"HTTP {r.status_code}")
        if r.status_code >= 400:
            raise ScraperError(f"HTTP {r.status_code}")
        marker = looks_blocked(r.text, block_markers)
        if marker:
            raise ScraperBlocked(f"anti-bot page ('{marker}')")
        return r.text

    async def post_json(self, url: str, payload: dict, headers: dict | None = None) -> dict:
        r = await self.request("POST", url, json=payload, headers={"Accept": "application/json", **(headers or {})}, min_interval=0.3)
        if r.status_code in (401, 403, 429):
            raise ScraperBlocked(f"HTTP {r.status_code}")
        if r.status_code >= 400:
            raise ScraperError(f"HTTP {r.status_code}")
        return r.json()


PRICE_RE = re.compile(r"£\s*([\d,]+(?:\.\d{1,2})?)")


def parse_price(text: str | None) -> float | None:
    if not text:
        return None
    m = PRICE_RE.search(text.replace("\xa0", " ").replace(" | ", ""))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_distance(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(mi|miles?)\b", text, re.I)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*km\b", text, re.I)
    if m:
        return round(float(m.group(1)) * 0.621371, 1)
    return None


def stable_id(source: str, url: str) -> str:
    return f"{source}:{hashlib.sha1(url.encode()).hexdigest()[:12]}"
