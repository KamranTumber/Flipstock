"""Facebook Marketplace adapter.

Marketplace is a client-rendered app, so a headless Chromium (Playwright) renders the
page. Supplying your own ``c_user`` / ``xs`` cookies (from a logged-in browser) enables
authenticated local-radius search. Without them Facebook usually shows a login wall,
which we report as ``login_required`` rather than failing silently.

``parse_marketplace_html`` is a pure function over rendered HTML so it can be unit
tested against saved pages and reused if you export a page manually.
"""

from __future__ import annotations

import re
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from ..config import get_settings
from ..schemas import GeoPoint, Listing
from .base import LoginRequired, parse_distance, parse_price, stable_id
from .browser import browser_pool

BASE = "https://www.facebook.com"
LOGIN_MARKERS = ('id="login_form"', 'name="login"', "log in to facebook", "log into facebook", "you must log in")


def location_slug(geo: GeoPoint) -> str:
    override = get_settings().fb_location_slug.strip()
    if override:
        return override
    district = (geo.district or "").lower()
    district = re.sub(r"^(city of|royal borough of|london borough of)\s+", "", district)
    slug = re.sub(r"[^a-z]", "", district.split(",")[0])
    return slug or "london"


def search_url(query: str, geo: GeoPoint, radius_miles: int) -> str:
    params = {"query": query, "exact": "false", "sortBy": "creation_time_descend"}
    if radius_miles:
        params["radius"] = str(max(1, round(radius_miles * 1.609)))  # FB uses km
    return f"{BASE}/marketplace/{location_slug(geo)}/search/?{urlencode(params)}"


def parse_marketplace_html(html: str, demo: bool = False) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[Listing] = []
    seen: set[str] = set()
    for a in soup.select('a[href*="/marketplace/item/"]'):
        m = re.search(r"/marketplace/item/(\d+)", a.get("href", ""))
        if not m:
            continue
        url = f"{BASE}/marketplace/item/{m.group(1)}/"
        if url in seen:
            continue
        lines = [l.strip() for l in a.get_text("\n").split("\n") if l.strip()]
        price_line = next((l for l in lines if l.startswith("£") or l.lower() == "free"), None)
        if not price_line or price_line.lower() == "free":
            continue
        price = parse_price(price_line)
        rest = [l for l in lines if not l.startswith("£") and l.lower() != "free"]
        if price is None or not rest:
            continue
        title = rest[0]
        location = rest[1] if len(rest) > 1 else None
        img = a.find("img")
        seen.add(url)
        out.append(
            Listing(
                id=stable_id("facebook", url),
                source="facebook",
                title=title,
                price=price,
                listing_type="classified",
                location=location,
                distance_miles=parse_distance(" ".join(rest[2:])) if len(rest) > 2 else None,
                image_url=img.get("src") if img else None,
                url=url,
                is_collection=True,
                is_demo=demo,
            )
        )
    return out


def session_cookies(c_user: str, xs: str) -> list[dict]:
    if not (c_user and xs):
        return []
    common = {"domain": ".facebook.com", "path": "/", "secure": True, "sameSite": "None"}
    return [
        {"name": "c_user", "value": c_user.strip(), "httpOnly": False, **common},
        {"name": "xs", "value": xs.strip(), "httpOnly": True, **common},
    ]


class FacebookScraper:
    name = "facebook"
    label = "FB Marketplace"

    def __init__(self, c_user: str = "", xs: str = "") -> None:
        self.cookies = session_cookies(c_user, xs)

    @property
    def authenticated(self) -> bool:
        return bool(self.cookies)

    async def search(self, query: str, geo: GeoPoint, radius: int, limit: int) -> list[Listing]:
        url = search_url(query, geo, radius)
        html = await browser_pool.render(
            url,
            cookies=self.cookies or None,
            wait_selector='a[href*="/marketplace/item/"]',
            scroll=2,
        )
        items = parse_marketplace_html(html)
        if not items:
            low = html.lower()
            login_wall = any(m in low for m in LOGIN_MARKERS)
            if self.authenticated and login_wall:
                raise LoginRequired("Facebook rejected the saved session cookies (expired?) — refresh c_user / xs")
            if not self.authenticated:
                # Logged-out Marketplace almost always renders no listings; don't report "0 results" as success.
                raise LoginRequired("Login cookie required")
        return items[:limit]
