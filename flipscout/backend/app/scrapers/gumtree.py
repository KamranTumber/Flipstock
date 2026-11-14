"""Gumtree UK adapter (server-rendered search results, parsed via stable data-q attributes)."""

from __future__ import annotations

import re
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from ..schemas import GeoPoint, Listing
from .base import Http, parse_distance, parse_price, stable_id

BASE = "https://www.gumtree.com"
GUMTREE_BLOCK_MARKERS = ("captcha-delivery.com", "datadome", "please enable js and disable any ad blocker")


def search_url(query: str, postcode: str | None, radius: int, page: int = 1) -> str:
    p: dict[str, str | int] = {"search_category": "all", "q": query}
    if radius and postcode:
        p["search_location"] = postcode.replace(" ", "")
        p["distance"] = radius
    else:
        p["search_location"] = "uk"
    if page > 1:
        p["page"] = page
    return f"{BASE}/search?{urlencode(p)}"


def parse_results(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[Listing] = []
    seen: set[str] = set()
    for tile in soup.select('[data-q="search-result"]'):
        a = tile.select_one('[data-q="search-result-anchor"]') or tile.find("a", href=True)
        if not a or not a.get("href"):
            continue
        url = urljoin(BASE, a["href"].split("?")[0])
        if url in seen:
            continue
        seen.add(url)

        def q(name: str) -> str:
            el = tile.select_one(f'[data-q="{name}"]')
            return el.get_text(" | ", strip=True) if el else ""

        title = q("tile-title")
        price = parse_price(q("tile-price"))
        if not title or price is None or price <= 0:
            continue  # "swap"/"free"/price-on-request ads aren't flippable comps
        location = q("tile-location") or None
        posted = q("tile-datePosted") or q("listing-posted-date") or None
        desc = q("tile-description") or None
        img = tile.find("img")
        image = None
        if img:
            image = img.get("src") or img.get("data-src")
            if image and image.startswith("data:"):
                image = img.get("data-src")
        attrs_text = tile.get_text(" ", strip=True)
        out.append(
            Listing(
                id=stable_id("gumtree", url),
                source="gumtree",
                title=re.sub(r"\s+", " ", title),
                price=price,
                postage=None,
                listing_type="classified",
                location=location,
                distance_miles=parse_distance(location) or parse_distance(attrs_text),
                image_url=image,
                url=url,
                posted_at=posted,
                description=(desc or "")[:400] or None,
                is_collection=True,
            )
        )
    return out


class GumtreeScraper:
    name = "gumtree"
    label = "Gumtree"

    def __init__(self, http: Http) -> None:
        self.http = http

    async def search(self, query: str, geo: GeoPoint, radius: int, limit: int) -> list[Listing]:
        html = await self.http.get_html(search_url(query, geo.postcode, radius), block_markers=GUMTREE_BLOCK_MARKERS)
        items = parse_results(html)
        if len(items) < limit // 2 and len(items) >= 20:
            html = await self.http.get_html(search_url(query, geo.postcode, radius, page=2), block_markers=GUMTREE_BLOCK_MARKERS)
            items += [i for i in parse_results(html) if i.url not in {x.url for x in items}]
        return items[:limit]
