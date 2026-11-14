"""Deterministic demo data so the app is explorable offline or when sources block.

Every listing produced here has ``is_demo=True`` and the UI labels it as DEMO DATA.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from urllib.parse import quote_plus

from rapidfuzz import fuzz

from ..schemas import CexBox, GeoPoint, Listing, SoldComp
from .base import stable_id


@dataclass(frozen=True)
class Product:
    name: str
    sold: float
    cash: float
    voucher: float
    retail: float


CATALOG = [
    Product("Sony PlayStation 5 Disc Console 825GB", 340, 300, 347, 470),
    Product("Sony PS5 Slim Digital Edition 1TB", 300, 230, 270, 380),
    Product("Nintendo Switch OLED White", 210, 150, 180, 260),
    Product("Xbox Series X 1TB Console", 290, 210, 250, 380),
    Product("Steam Deck OLED 512GB", 390, 280, 320, 480),
    Product("NVIDIA GeForce RTX 3080 10GB Founders Edition", 330, 260, 300, 420),
    Product("MSI GeForce RTX 4070 Ventus 2X 12GB", 430, 330, 380, 550),
    Product("AMD Radeon RX 6800 XT 16GB", 330, 250, 290, 420),
    Product("Apple iPhone 13 128GB Unlocked", 270, 190, 225, 330),
    Product("Apple iPhone 14 Pro 256GB Unlocked", 520, 380, 430, 620),
    Product("Apple iPad Air 5th Gen 64GB WiFi", 330, 230, 270, 400),
    Product("Apple MacBook Air M1 8GB 256GB", 450, 330, 380, 520),
    Product("Apple AirPods Pro 2nd Gen", 120, 70, 85, 140),
    Product("Sony WH-1000XM5 Wireless Headphones", 180, 110, 130, 220),
    Product("Logitech G Pro X Superlight Mouse", 70, 35, 45, 85),
]

PREFIXES = ["", "", "RARE ", "Boxed ", "MINT ", "L@@K "]
SUFFIXES = ["", " - collection only", " boxed", " excellent condition", " bundle", " + charger", " (quick sale)"]
BAD_SUFFIXES = [" - spares or repairs", " box only", " iCloud locked", " faulty - read description"]
TOWNS = ["Crawley", "East Grinstead", "Horsham", "Redhill", "Tunbridge Wells", "Brighton", "Croydon", "Guildford"]


def _rng(*parts: str) -> random.Random:
    return random.Random(int(hashlib.md5("|".join(parts).encode()).hexdigest()[:8], 16))


def products_for(query: str) -> list[Product]:
    q = (query or "").strip()
    if not q:
        return CATALOG[:6]
    from ..services.normalizer import match_score

    scored = sorted(((match_score(q, p.name).score, p) for p in CATALOG), key=lambda x: -x[0])
    hits = [p for s, p in scored if s >= 62]
    if not hits:  # loose fallback for free-text queries like "graphics card"
        scored = sorted(((fuzz.token_set_ratio(q.lower(), p.name.lower()), p) for p in CATALOG), key=lambda x: -x[0])
    return hits[:5] or [p for _, p in scored[:4]]


def demo_listings(source: str, query: str, geo: GeoPoint, radius: int, limit: int = 12) -> list[Listing]:
    rng = _rng(source, query, geo.outcode)
    out: list[Listing] = []
    prods = products_for(query)
    for i in range(min(limit, 4 * len(prods))):
        p = prods[i % len(prods)]
        bad = rng.random() < 0.12
        title = rng.choice(PREFIXES) + p.name + (rng.choice(BAD_SUFFIXES) if bad else rng.choice(SUFFIXES))
        price = round(p.sold * rng.uniform(0.55, 1.0) * (0.4 if bad else 1), 0)
        dist = round(rng.uniform(0.5, radius or 60), 1)
        url = {
            "ebay": f"https://www.ebay.co.uk/sch/i.html?_nkw={quote_plus(p.name)}",
            "gumtree": f"https://www.gumtree.com/search?q={quote_plus(p.name)}",
            "facebook": f"https://www.facebook.com/marketplace/search/?query={quote_plus(p.name)}",
        }[source] + f"&demo={i}"
        is_ebay = source == "ebay"
        auction = is_ebay and rng.random() < 0.3
        out.append(
            Listing(
                id=stable_id(source, url),
                source=source,  # type: ignore[arg-type]
                title=title.strip(),
                price=price,
                postage=round(rng.choice([0, 3.99, 4.95, 6.99]), 2) if is_ebay else None,
                condition="Pre-owned" if is_ebay else None,
                listing_type="auction" if auction else ("buy_it_now" if is_ebay else "classified"),
                bids=rng.randint(0, 9) if auction else None,
                time_left=f"{rng.randint(0, 2)}d {rng.randint(1, 23)}h left" if auction else None,
                seller_feedback=f"99.{rng.randint(0, 9)}% positive ({rng.randint(5, 3000)})" if is_ebay else None,
                location=f"{rng.choice(TOWNS)}",
                distance_miles=None if is_ebay else dist,
                url=url,
                posted_at=None if is_ebay else f"{rng.randint(1, 23)} hours ago",
                is_collection=not is_ebay,
                is_demo=True,
            )
        )
    return out


def demo_sold(query: str) -> list[SoldComp]:
    out: list[SoldComp] = []
    for p in products_for(query):
        rng = _rng("sold", p.name)
        for i in range(rng.randint(9, 18)):
            out.append(
                SoldComp(
                    title=p.name + rng.choice(["", " boxed", " - excellent", " used"]),
                    price=round(p.sold * rng.uniform(0.85, 1.15), 2),
                    shipping=rng.choice([0, 3.99, 5.99]),
                    condition="Pre-owned",
                    sold_date=f"{rng.randint(1, 28)} Oct 2026",
                    url=f"https://www.ebay.co.uk/sch/i.html?_nkw={quote_plus(p.name)}&LH_Sold=1&demo={i}",
                )
            )
    return out


def demo_cex(query: str) -> list[CexBox]:
    return [
        CexBox(
            box_id=f"DEMO{i}",
            name=p.name + ", B",
            category="Demo",
            cash=p.cash,
            voucher=p.voucher,
            retail=p.retail,
            url=f"https://uk.webuy.com/search?stext={quote_plus(p.name)}",
        )
        for i, p in enumerate(products_for(query))
    ]
