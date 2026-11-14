"""eBay UK adapter.

Active listings:  official Browse API when EBAY_CLIENT_ID/SECRET are set, otherwise the
                  public search results page (eBay often refuses automated requests; when
                  it does we surface a "blocked" status instead of failing silently).
Sold comps:       public sold/completed search page (LH_Sold=1&LH_Complete=1). If that is
                  refused and the Browse API is configured, an *estimate* from active
                  Buy-It-Now prices is used and clearly labelled as such.
"""

from __future__ import annotations

import base64
import logging
import re
import time
from typing import Literal
from urllib.parse import urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup

from ..config import get_settings
from ..schemas import GeoPoint, Listing, SoldComp
from .base import Http, ScraperBlocked, ScraperError, parse_distance, parse_price, stable_id

log = logging.getLogger(__name__)

SEARCH = "https://www.ebay.co.uk/sch/i.html"
API = "https://api.ebay.com"
EBAY_BLOCK_MARKERS = ("pardon our interruption", "splashui/challenge", "/captcha")


# ------------------------------------------------------------------ URL builders


def active_url(query: str, postcode: str | None, mode: Literal["bin", "auction"] = "bin") -> str:
    p: dict[str, str | int] = {"_nkw": query, "LH_PrefLoc": 1, "_ipg": 60}
    if postcode:
        p["_stpos"] = postcode.replace(" ", "")
    if mode == "bin":
        p.update({"LH_BIN": 1, "_sop": 7})  # nearest first
    else:
        p.update({"LH_Auction": 1, "_sop": 1})  # ending soonest
    return f"{SEARCH}?{urlencode(p)}"


def sold_url(query: str) -> str:
    p = {"_nkw": query, "LH_Sold": 1, "LH_Complete": 1, "LH_PrefLoc": 1, "_ipg": 120, "_sop": 13}
    return f"{SEARCH}?{urlencode(p)}"


def clean_item_url(href: str) -> str:
    m = re.search(r"/itm/(?:[^/?]+/)?(\d{9,})", href or "")
    if m:
        return f"https://www.ebay.co.uk/itm/{m.group(1)}"
    u = urlparse(href or "")
    return urlunparse(u._replace(query="", fragment=""))


# ------------------------------------------------------------------ HTML parsing


def _txt(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


def _postage(text: str) -> tuple[float | None, bool]:
    """-> (postage £ or None if unknown, collection_only)."""
    t = text.lower()
    if not t:
        return None, False
    if "collection" in t and not re.search(r"postage|delivery|£", t.replace("free collection", "")):
        return None, True
    if "free" in t and ("postage" in t or "delivery" in t or "shipping" in t):
        return 0.0, False
    p = parse_price(text)
    if p is not None:
        return p, False
    return None, False


def parse_search_html(html: str, *, sold: bool = False) -> list[dict]:
    """Parse an eBay search results page into plain dicts. Supports s-item and s-card markup."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict] = []
    for it in soup.select("li.s-item, li.s-card, div.s-card"):
        title_el = it.select_one(".s-item__title, .s-card__title")
        title = _txt(title_el)
        title = re.sub(r"^(New listing|NEW LISTING)\s*", "", title)
        title = re.sub(r"\s*Opens in a new window or tab\s*$", "", title, flags=re.I).strip()
        if not title or title.lower().startswith("shop on ebay"):
            continue
        link = it.select_one("a.s-item__link, a.su-link, a[href*='/itm/']")
        if not link or not link.get("href"):
            continue
        url = clean_item_url(link["href"])

        price_text = _txt(it.select_one(".s-item__price, .s-card__price"))
        if " to " in price_text:  # variation range: ambiguous
            continue
        price = parse_price(price_text)
        if price is None:
            continue

        rows = [
            _txt(r)
            for r in it.select(
                ".s-item__detail, .s-item__subtitle, .s-card__attribute-row, .s-card__subtitle, .s-card__caption, .s-item__caption"
            )
        ]
        rows = [r for r in rows if r]
        blob = " | ".join(rows)

        ship_text = _txt(it.select_one(".s-item__shipping, .s-item__logisticsCost, .s-item__freeXDays"))
        if not ship_text:
            ship_text = next((r for r in rows if re.search(r"postage|delivery|collection", r, re.I)), "")
        postage, collection = _postage(ship_text)

        condition = _txt(it.select_one(".SECONDARY_INFO, .s-card__subtitle"))
        if not condition:
            condition = next(
                (r for r in rows if re.search(r"pre-owned|brand new|refurbished|for parts|opened|used", r, re.I)), ""
            )
        condition = condition.split("|")[0].split("·")[0].strip() or None

        location = _txt(it.select_one(".s-item__location, .s-item__itemLocation"))
        if not location:
            location = next((r for r in rows if re.match(r"(from|located in)\b", r, re.I)), "")
        location = re.sub(r"^(from|located in:?)\s*", "", location, flags=re.I) or None

        seller = _txt(it.select_one(".s-item__seller-info-text"))
        if not seller:
            seller = next((r for r in rows if "% positive" in r.lower()), "")

        bids = None
        m = re.search(r"(\d+)\s+bids?\b", _txt(it.select_one(".s-item__bids")) or blob)
        if m:
            bids = int(m.group(1))
        time_left = _txt(it.select_one(".s-item__time-left")) or next((r for r in rows if r.lower().endswith(" left")), "")

        sold_date = None
        if sold:
            cap = _txt(it.select_one(".s-item__caption--signal, .s-item__title--tagblock .POSITIVE, .s-card__caption")) or blob
            m = re.search(r"Sold\s+(\d{1,2}\s+\w{3},?\s+\d{4})", cap)
            sold_date = m.group(1) if m else None

        img = it.select_one("img")
        image = None
        if img:
            image = img.get("src") or img.get("data-src") or img.get("data-defer-load")
            if image and image.startswith("data:"):
                image = img.get("data-src") or None

        out.append(
            dict(
                title=title,
                url=url,
                price=price,
                postage=postage,
                collection=collection,
                condition=condition,
                location=location,
                distance=parse_distance(location) or parse_distance(blob),
                seller=seller or None,
                bids=bids,
                time_left=time_left or None,
                sold_date=sold_date,
                image=image,
                auction=bids is not None or bool(time_left),
            )
        )
    return out


def dicts_to_listings(rows: list[dict]) -> list[Listing]:
    out = []
    for r in rows:
        out.append(
            Listing(
                id=stable_id("ebay", r["url"]),
                source="ebay",
                title=r["title"],
                price=r["price"],
                postage=r["postage"],
                condition=r["condition"],
                listing_type="auction" if r["auction"] else "buy_it_now",
                bids=r["bids"],
                time_left=r["time_left"],
                seller_feedback=r["seller"],
                location=r["location"],
                distance_miles=r["distance"],
                image_url=r["image"],
                url=r["url"],
                is_collection=r["collection"],
            )
        )
    return out


def dicts_to_sold(rows: list[dict]) -> list[SoldComp]:
    return [
        SoldComp(
            title=r["title"],
            price=r["price"],
            shipping=r["postage"],
            condition=r["condition"],
            sold_date=r["sold_date"],
            url=r["url"],
            image_url=r["image"],
        )
        for r in rows
    ]


# ------------------------------------------------------------------ Browse API

_token: dict[str, float | str] = {"value": "", "expires": 0.0, "client": ""}


def ebay_credentials() -> tuple[str, str]:
    """Keys from the Settings panel, falling back to EBAY_CLIENT_ID / EBAY_CLIENT_SECRET in .env."""
    from ..services.user_settings import load_user_settings

    us = load_user_settings()
    return us.ebay_client_id, us.ebay_client_secret


def api_configured() -> bool:
    cid, secret = ebay_credentials()
    return bool(cid and secret)


async def _api_token(http: Http) -> str:
    cid, secret = ebay_credentials()
    if not (cid and secret):
        raise ScraperError("eBay API keys are not set")
    if _token["value"] and _token["client"] == cid and time.time() < float(_token["expires"]) - 60:
        return str(_token["value"])
    basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    r = await http.request(
        "POST",
        f"{API}/identity/v1/oauth2/token",
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
        content="grant_type=client_credentials&scope=https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope",
        min_interval=0,
    )
    if r.status_code != 200:
        detail = ""
        try:
            body = r.json()
            detail = body.get("error_description") or body.get("error") or ""
        except ValueError:
            pass
        hint = " (are these Sandbox keys? FlipScout needs Production keys)" if "SBX" in cid.upper() else ""
        raise ScraperError(f"eBay API auth failed (HTTP {r.status_code}{': ' + detail if detail else ''}){hint}")
    data = r.json()
    _token.update(value=data["access_token"], expires=time.time() + int(data.get("expires_in", 7200)), client=cid)
    return str(_token["value"])


async def test_connection(http: Http, query: str = "ps5 console") -> dict:
    """Used by the Settings 'Test connection' button: auth + one small search."""
    _token["value"] = ""  # force a fresh token so key changes are actually tested
    t0 = time.perf_counter()
    items = await api_search(http, query, None, "bin", 5)
    return {
        "ok": True,
        "message": f"Connected — eBay API returned {len(items)} live UK listings for “{query}”",
        "sample": [{"title": i.title, "price": i.price, "url": i.url} for i in items[:3]],
        "elapsed_ms": int((time.perf_counter() - t0) * 1000),
    }


def _api_item_to_listing(it: dict) -> Listing:
    auction = "AUCTION" in (it.get("buyingOptions") or []) and "FIXED_PRICE" not in (it.get("buyingOptions") or [])
    price_obj = (it.get("currentBidPrice") if auction else None) or it.get("price") or {}
    ship = None
    for opt in it.get("shippingOptions") or []:
        cost = (opt.get("shippingCost") or {}).get("value")
        if cost is not None:
            ship = float(cost)
            break
    loc = it.get("itemLocation") or {}
    loc_text = ", ".join(x for x in [loc.get("city"), (loc.get("postalCode") or "").replace("*", "").strip()] if x) or None
    seller = it.get("seller") or {}
    fb = f"{seller.get('feedbackPercentage', '?')}% positive ({seller.get('feedbackScore', '?')})" if seller else None
    dist = (it.get("distanceFromPickupLocation") or {}).get("value")
    url = clean_item_url(it.get("itemWebUrl", ""))
    return Listing(
        id=stable_id("ebay", url),
        source="ebay",
        title=it.get("title", ""),
        price=float(price_obj.get("value", 0) or 0),
        postage=ship,
        condition=it.get("condition"),
        listing_type="auction" if auction else "buy_it_now",
        bids=it.get("bidCount"),
        time_left=it.get("itemEndDate"),
        seller_feedback=fb,
        location=loc_text,
        distance_miles=float(dist) if dist is not None else None,
        image_url=(it.get("image") or {}).get("imageUrl"),
        url=url,
        is_collection=ship is None and bool(it.get("pickupOptions")),
    )


async def api_search(
    http: Http, query: str, geo: GeoPoint | None, mode: Literal["bin", "auction"], limit: int, radius: int = 0, local_only: bool = False
) -> list[Listing]:
    token = await _api_token(http)
    filters = ["itemLocationCountry:GB", "priceCurrency:GBP", "buyingOptions:{FIXED_PRICE}" if mode == "bin" else "buyingOptions:{AUCTION}"]
    if local_only and geo and radius:
        filters += ["pickupCountry:GB", f"pickupPostalCode:{geo.postcode.replace(' ', '')}", f"pickupRadius:{radius}", "pickupRadiusUnit:mi"]
    params = {"q": query, "limit": min(limit, 200), "filter": ",".join(filters)}
    params["sort"] = "endingSoonest" if mode == "auction" else "newlyListed"
    headers = {"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB"}
    if geo:
        headers["X-EBAY-C-ENDUSERCTX"] = f"contextualLocation=country%3DGB%2Czip%3D{geo.postcode.replace(' ', '')}"
    r = await http.request("GET", f"{API}/buy/browse/v1/item_summary/search", params=params, headers=headers, min_interval=0.2)
    if r.status_code == 429:
        raise ScraperBlocked("eBay API rate limit reached")
    if r.status_code != 200:
        raise ScraperError(f"eBay API HTTP {r.status_code}")
    return [_api_item_to_listing(i) for i in r.json().get("itemSummaries") or []]


# ------------------------------------------------------------------ public adapter


class EbayScraper:
    name = "ebay"
    label = "eBay UK"

    def __init__(self, http: Http) -> None:
        self.http = http

    async def search_active(self, query: str, geo: GeoPoint, radius: int, limit: int) -> list[Listing]:
        if api_configured():
            bin_items = await api_search(self.http, query, geo, "bin", limit, radius)
            auc_items = await api_search(self.http, query, geo, "auction", max(10, limit // 3), radius)
            return (bin_items + auc_items)[: limit + limit // 3]
        try:
            html = await self.http.get_html(active_url(query, geo.postcode, "bin"), block_markers=EBAY_BLOCK_MARKERS)
        except ScraperBlocked as e:
            raise ScraperBlocked(
                f"eBay refused the request ({e}). Add free EBAY_CLIENT_ID / EBAY_CLIENT_SECRET keys to use the official API."
            ) from e
        items = dicts_to_listings(parse_search_html(html))
        try:
            html = await self.http.get_html(active_url(query, geo.postcode, "auction"), block_markers=EBAY_BLOCK_MARKERS)
            items += dicts_to_listings(parse_search_html(html))[: max(10, limit // 3)]
        except ScraperError:
            pass  # BIN results are enough
        return items[: limit + limit // 3]

    async def search_sold(self, query: str) -> list[SoldComp]:
        html = await self.http.get_html(sold_url(query), block_markers=EBAY_BLOCK_MARKERS)
        return dicts_to_sold(parse_search_html(html, sold=True))

    async def active_prices(self, query: str) -> list[SoldComp]:
        """Fallback valuation input: active BIN prices via the official API."""
        items = await api_search(self.http, query, None, "bin", 50)
        return [
            SoldComp(title=i.title, price=i.price, shipping=i.postage, condition=i.condition, url=i.url, image_url=i.image_url)
            for i in items
        ]
