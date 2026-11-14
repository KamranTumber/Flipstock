"""Turns raw comp pools (eBay sold, CeX boxes, FB active listings) into per-listing valuations."""

from __future__ import annotations

import re
import statistics

from ..schemas import CexBox, EbayValuation, FbValuation, Listing, SoldComp, UserSettings
from .normalizer import condition_bucket, match_score, red_flags


def trim_outliers(prices: list[float]) -> list[float]:
    if len(prices) < 5:
        return prices
    q = statistics.quantiles(prices, n=4)
    q1, q3 = q[0], q[2]
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    kept = [p for p in prices if lo <= p <= hi]
    return kept or prices


def ebay_valuation(
    title: str,
    source_condition: str | None,
    pool: list[SoldComp],
    threshold: float,
    comps_url: str,
    method: str = "sold",
) -> EbayValuation | None:
    src_bucket = condition_bucket(source_condition, title)
    scored: list[SoldComp] = []
    seen: set[str] = set()
    for c in pool:
        if c.url in seen:
            continue
        seen.add(c.url)
        if condition_bucket(c.condition, c.title) == "parts":
            continue
        s = match_score(title, c.title).score
        if s >= threshold:
            scored.append(c.model_copy(update={"match_score": s}))
    if not scored:
        return None
    same = [c for c in scored if condition_bucket(c.condition, c.title) == src_bucket]
    if len(same) >= 3:
        scored = same
    prices = trim_outliers([c.price for c in scored])
    ships = [c.shipping for c in scored if c.shipping is not None]
    if method == "active_estimate":
        # Asking prices overstate what things actually sell for.
        prices = [p * 0.9 for p in prices]
    return EbayValuation(
        median=round(statistics.median(prices), 2),
        mean=round(statistics.fmean(prices), 2),
        low=round(min(prices), 2),
        high=round(max(prices), 2),
        avg_shipping=round(statistics.fmean(ships), 2) if ships else None,
        sample_size=len(prices),
        method=method,  # type: ignore[arg-type]
        comps_url=comps_url,
        comps=sorted(scored, key=lambda c: -(c.match_score or 0))[:6],
    )


def _cex_match_name(name: str) -> str:
    return re.sub(r",\s*[A-C]$", "", name)  # strip CeX grade suffix


def best_cex_match(title: str, boxes: list[CexBox], threshold: float) -> CexBox | None:
    best: CexBox | None = None
    best_score = -1.0
    for b in boxes:
        s = match_score(title, _cex_match_name(b.name)).score
        # Prefer boxes CeX will actually buy.
        rank = s + (2 if b.cash else 0)
        if s >= threshold and rank > best_score:
            best, best_score = b.model_copy(update={"match_score": s}), rank
    return best


def fb_valuation(
    listing: Listing,
    fb_pool: list[Listing],
    ebay_val: EbayValuation | None,
    s: UserSettings,
    threshold: float,
) -> FbValuation | None:
    matched = [
        l.price
        for l in fb_pool
        if l.id != listing.id and not red_flags(l.title) and match_score(listing.title, l.title).score >= threshold
    ]
    if len(matched) >= 3:
        med = statistics.median(trim_outliers(matched))
        return FbValuation(
            value=round(med * s.fb_active_discount, 2),
            method="active_comps",
            sample_size=len(matched),
            note=f"Median of {len(matched)} active local listings × {s.fb_active_discount:.0%} (haggle discount)",
        )
    if ebay_val:
        return FbValuation(
            value=round(ebay_val.median * s.fb_local_factor, 2),
            method="heuristic",
            sample_size=0,
            note=f"Estimate: {s.fb_local_factor:.0%} of eBay sold median (not enough local FB comps)",
        )
    return None
