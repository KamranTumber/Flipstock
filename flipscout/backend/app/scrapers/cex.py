"""CeX (uk.webuy.com) adapter via the public Algolia search index the site itself uses."""

from __future__ import annotations

from ..config import get_settings
from ..schemas import CexBox
from .base import Http, ScraperError

PRODUCT_URL = "https://uk.webuy.com/product-detail?id={}"


def hit_to_box(h: dict) -> CexBox | None:
    box_id = h.get("boxId") or h.get("objectID")
    name = h.get("boxName")
    if not box_id or not name:
        return None

    def num(*keys):
        for k in keys:
            v = h.get(k)
            if isinstance(v, (int, float)) and v > 0:
                return float(v)
        return None

    imgs = h.get("imageUrls") or {}
    return CexBox(
        box_id=str(box_id),
        name=name,
        category=h.get("categoryFriendlyName") or h.get("categoryName"),
        cash=num("cashPriceCalculated", "cashPrice"),
        voucher=num("exchangePriceCalculated", "exchangePrice"),
        retail=num("sellPrice"),
        image_url=(imgs.get("medium") or imgs.get("large") or "").replace(" ", "%20") or None,
        url=PRODUCT_URL.format(box_id),
    )


class CexClient:
    name = "cex"
    label = "CeX"

    def __init__(self, http: Http) -> None:
        self.http = http

    async def search(self, query: str, hits: int = 30) -> list[CexBox]:
        cfg = get_settings()
        url = f"https://search.webuy.io/1/indexes/{cfg.cex_algolia_index}/query"
        headers = {
            "x-algolia-application-id": cfg.cex_algolia_app_id,
            "x-algolia-api-key": cfg.cex_algolia_api_key,
            "Origin": "https://uk.webuy.com",
            "Referer": "https://uk.webuy.com/",
        }
        try:
            data = await self.http.post_json(url, {"query": query, "hitsPerPage": hits}, headers=headers)
        except ScraperError as e:
            raise ScraperError(f"CeX search failed ({e}); CeX may have rotated its search key — see CEX_ALGOLIA_* in .env") from e
        boxes = [hit_to_box(h) for h in data.get("hits") or []]
        # Boxes CeX won't buy (cash/voucher missing) still give a retail ceiling.
        return [b for b in boxes if b is not None]
