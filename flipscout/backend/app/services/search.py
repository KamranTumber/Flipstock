"""Search orchestrator: geocode -> source in parallel -> comps in parallel -> deals."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from sqlmodel import select

from ..config import get_settings
from ..db import session_scope
from ..models import SoldPrice
from ..schemas import (
    CexBox,
    Deal,
    GeoPoint,
    Listing,
    SearchRequest,
    SearchResponse,
    SoldComp,
    SourceStatus,
    UserSettings,
)
from ..scrapers import demo
from ..scrapers.base import BrowserUnavailable, Http, LoginRequired, ScraperBlocked, ScraperError
from ..scrapers.cex import CexClient
from ..scrapers.ebay import EbayScraper, api_configured, sold_url
from ..scrapers.facebook import FacebookScraper
from ..scrapers.gumtree import GumtreeScraper
from . import profit as P
from .cache import cache_get, cache_set
from .comps import best_cex_match, ebay_valuation, fb_valuation
from .geocode import GeocodeError, geocode_place, geocode_postcode, haversine_miles
from .normalizer import comp_query, detect_category, normalize_title, red_flags
from .user_settings import load_user_settings

log = logging.getLogger(__name__)

Emit = Callable[[dict], Awaitable[None]]

PRESETS: dict[str, dict[str, Any]] = {
    "gpus": {"label": "PC Components / GPUs", "queries": ["rtx 3080", "rtx 4070", "rx 6800 xt"]},
    "apple": {"label": "Apple Products", "queries": ["iphone 13", "iphone 14 pro", "macbook air m1"]},
    "consoles": {"label": "Consoles", "queries": ["ps5 console", "nintendo switch oled", "xbox series x"]},
    "audio": {"label": "Audio / Peripherals", "queries": ["airpods pro", "sony wh-1000xm5", "logitech g pro superlight"]},
}

LABELS = {
    "ebay": "eBay UK",
    "gumtree": "Gumtree",
    "facebook": "FB Marketplace",
    "ebay_sold": "eBay sold comps",
    "cex": "CeX",
}

# Description-level flags we trust (titles often omit them, descriptions admit them).
STRICT_DESC_FLAGS = {"spares/repairs", "faulty", "icloud locked", "box only", "network blacklisted"}
VAGUE_LOCATIONS = {"united kingdom", "uk", "gb", "england", "scotland", "wales", "northern ireland"}


class SearchError(Exception):
    pass


async def _noop(_: dict) -> None:
    return None


def _queries(req: SearchRequest) -> list[str]:
    if req.preset and req.preset in PRESETS:
        qs = list(PRESETS[req.preset]["queries"])
        if req.query.strip():
            qs = [req.query.strip()]
        return qs
    q = req.query.strip()
    if not q:
        raise SearchError("Enter a search term or choose a preset category.")
    return [q]


async def _cached(key: str, ttl: int, source: str, fetch: Callable[[], Awaitable[list]], model) -> tuple[list, bool]:
    hit = cache_get(key, ttl)
    if hit is not None:
        return [model(**x) for x in hit], True
    items = await fetch()
    if items:  # empty results are often transient; don't pin them for the TTL
        cache_set(key, source, [i.model_dump() for i in items])
    return items, False


def _status_for_exc(name: str, e: BaseException) -> SourceStatus:
    label = LABELS.get(name, name)
    if isinstance(e, LoginRequired):
        return SourceStatus(source=name, label=label, state="login_required", message=str(e) or "Login required")
    if isinstance(e, BrowserUnavailable):
        return SourceStatus(source=name, label=label, state="unavailable", message=str(e))
    if isinstance(e, ScraperBlocked):
        return SourceStatus(source=name, label=label, state="blocked", message=f"Blocked / rate-limited: {e}")
    if isinstance(e, ScraperError):
        return SourceStatus(source=name, label=label, state="error", message=str(e))
    log.exception("Unexpected error in %s", name, exc_info=e)
    return SourceStatus(source=name, label=label, state="error", message=f"Unexpected error: {e.__class__.__name__}: {e}")


async def _multi_query(
    name: str, queries: list[str], fetch_one: Callable[[str], Awaitable[tuple[list, bool]]]
) -> tuple[list, SourceStatus]:
    """Run one source across all queries; partial failures still return what worked."""
    t0 = time.perf_counter()
    items: list = []
    errors: list[BaseException] = []
    all_cached = True
    for q in queries:
        try:
            got, cached = await fetch_one(q)
            items += got
            all_cached = all_cached and cached
        except Exception as e:  # noqa: BLE001 - mapped to a status below
            errors.append(e)
            if isinstance(e, (LoginRequired, BrowserUnavailable, ScraperBlocked)):
                break  # don't keep hammering a source that has refused us
    ms = int((time.perf_counter() - t0) * 1000)
    if errors and not items:
        st = _status_for_exc(name, errors[0])
        st.elapsed_ms = ms
        return [], st
    msg = f"{len(items)} result{'s' if len(items) != 1 else ''}"
    if errors:
        msg += f" (partial: {errors[0]})"
    return items, SourceStatus(
        source=name, label=LABELS[name], state="cached" if all_cached and not errors else "ok", message=msg, count=len(items), elapsed_ms=ms
    )


def _record_sold(query: str, comps: list[SoldComp]) -> None:
    if not comps:
        return
    try:
        with session_scope() as s:
            urls = [c.url for c in comps]
            existing = set(s.exec(select(SoldPrice.url).where(SoldPrice.url.in_(urls))).all())  # type: ignore[attr-defined]
            for c in comps:
                if c.url in existing:
                    continue
                existing.add(c.url)
                s.add(SoldPrice(comp_query=query, title=c.title, price=c.price, shipping=c.shipping, condition=c.condition, sold_date=c.sold_date, url=c.url))
            s.commit()
    except Exception:
        log.exception("could not record sold prices")


class SearchRunner:
    def __init__(self, req: SearchRequest, emit: Emit | None = None) -> None:
        self.req = req
        self.emit = emit or _noop
        self.cfg = get_settings()
        self.us: UserSettings = load_user_settings()
        self.demo = req.demo or self.cfg.demo_mode
        self.statuses: dict[str, SourceStatus] = {}

    async def _status(self, st: SourceStatus) -> None:
        self.statuses[st.source] = st
        await self.emit({"type": "source", "status": st.model_dump()})

    # ------------------------------------------------------------- sourcing

    async def _source(self, http: Http, name: str, queries: list[str], geo: GeoPoint) -> list[Listing]:
        radius, limit = self.req.radius, self.cfg.max_listings_per_source
        await self.emit({"type": "source", "status": SourceStatus(source=name, label=LABELS[name], state="ok", message="Searching…").model_dump() | {"pending": True}})

        if self.demo:
            items = [l for q in queries for l in demo.demo_listings(name, q, geo, radius)]
            await self._status(SourceStatus(source=name, label=LABELS[name], state="demo", message=f"{len(items)} demo listings", count=len(items)))
            return items

        ttl = self.cfg.listing_cache_ttl_min
        if name == "ebay":
            scraper = EbayScraper(http)
            fetch = lambda q: _cached(f"ebay:{q}:{geo.postcode}:{radius}", ttl, "ebay", lambda: scraper.search_active(q, geo, radius, limit), Listing)  # noqa: E731
        elif name == "gumtree":
            scraper = GumtreeScraper(http)
            fetch = lambda q: _cached(f"gumtree:{q}:{geo.postcode}:{radius}", ttl, "gumtree", lambda: scraper.search(q, geo, radius, limit), Listing)  # noqa: E731
        else:
            fbs = FacebookScraper(self.us.fb_c_user, self.us.fb_xs)
            fetch = lambda q: _cached(f"facebook:{q}:{geo.postcode}:{radius}:{fbs.authenticated}", ttl, "facebook", lambda: fbs.search(q, geo, radius, limit), Listing)  # noqa: E731

        items, st = await _multi_query(name, queries, fetch)
        if name == "facebook" and st.state in ("login_required", "blocked", "unavailable", "error") and self.cfg.fb_fallback == "demo":
            items = [l for q in queries for l in demo.demo_listings("facebook", q, geo, radius)]
            st = SourceStatus(source=name, label=LABELS[name], state="demo", message=f"{st.message} — showing {len(items)} labelled demo listings", count=len(items))
        await self._status(st)
        return items

    # ------------------------------------------------------------- comps

    async def _sold_pool(self, http: Http, queries: list[str]) -> tuple[list[SoldComp], str, str]:
        """-> (comps, method, comps_url_for_first_query)."""
        if self.demo:
            pool = [c for q in queries for c in demo.demo_sold(q)]
            await self._status(SourceStatus(source="ebay_sold", label=LABELS["ebay_sold"], state="demo", message=f"{len(pool)} demo sold comps", count=len(pool)))
            return pool, "sold", sold_url(queries[0])

        eb = EbayScraper(http)
        ttl = self.cfg.comp_cache_ttl_min

        async def fetch(q: str):
            got, cached = await _cached(f"ebay_sold:{q}", ttl, "ebay_sold", lambda: eb.search_sold(q), SoldComp)
            if not cached:
                _record_sold(q, got)
            return got, cached

        pool, st = await _multi_query("ebay_sold", queries, fetch)
        method = "sold"
        if not pool and st.state in ("blocked", "error") and api_configured():
            async def fetch_active(q: str):
                return await _cached(f"ebay_active_est:{q}", ttl, "ebay_sold", lambda: eb.active_prices(q), SoldComp)

            pool, st2 = await _multi_query("ebay_sold", queries, fetch_active)
            if pool:
                method = "active_estimate"
                st = SourceStatus(
                    source="ebay_sold", label=LABELS["ebay_sold"], state="ok", count=len(pool), elapsed_ms=st.elapsed_ms + st2.elapsed_ms,
                    message=f"Sold page refused — estimating from {len(pool)} active Buy-It-Now prices (×90%)",
                )
        await self._status(st)
        return pool, method, sold_url(queries[0])

    async def _cex_pool(self, http: Http, queries: list[str]) -> list[CexBox]:
        if self.demo:
            boxes = [b for q in queries for b in demo.demo_cex(q)]
            await self._status(SourceStatus(source="cex", label="CeX", state="demo", message=f"{len(boxes)} demo boxes", count=len(boxes)))
            return boxes
        cx = CexClient(http)
        ttl = self.cfg.comp_cache_ttl_min
        boxes, st = await _multi_query("cex", queries, lambda q: _cached(f"cex:{q}", ttl, "cex", lambda: cx.search(q), CexBox))
        await self._status(st)
        return boxes

    # ------------------------------------------------------------- distance

    async def _fill_distances(self, http: Http, geo: GeoPoint, listings: list[Listing]) -> None:
        todo = {
            l.location.strip()
            for l in listings
            if l.distance_miles is None and l.location and l.location.strip().lower() not in VAGUE_LOCATIONS
        }
        sem = asyncio.Semaphore(5)
        coords: dict[str, tuple[float, float] | None] = {}

        async def one(loc: str):
            async with sem:
                coords[loc] = await geocode_place(loc, http.client, near=(geo.latitude, geo.longitude))

        await asyncio.gather(*(one(l) for l in todo))
        for l in listings:
            if l.distance_miles is None and l.location:
                c = coords.get(l.location.strip())
                if c:
                    l.distance_miles = round(haversine_miles(geo.latitude, geo.longitude, c[0], c[1]), 1)

    # ------------------------------------------------------------- main

    async def run(self) -> SearchResponse:
        t0 = time.perf_counter()
        req = self.req
        queries = _queries(req)
        await self.emit({"type": "stage", "stage": "geocode", "message": f"Locating {req.postcode}…"})
        http = Http()
        try:
            try:
                geo = await geocode_postcode(req.postcode, http.client)
            except GeocodeError as e:
                raise SearchError(str(e)) from e
            await self.emit({"type": "geo", "geo": geo.model_dump()})

            # 1) Sourcing + comp pools, all in parallel.
            await self.emit({"type": "stage", "stage": "sourcing", "message": f"Searching {', '.join(LABELS[s] for s in req.sources)} for {', '.join(queries)}…"})
            source_tasks = [self._source(http, s, queries, geo) for s in req.sources]
            sold_task = self._sold_pool(http, queries)
            cex_task = self._cex_pool(http, queries)
            results = await asyncio.gather(*source_tasks, sold_task, cex_task)
            source_lists: list[list[Listing]] = list(results[: len(source_tasks)])
            sold_pool, sold_method, base_comps_url = results[len(source_tasks)]
            cex_pool: list[CexBox] = results[len(source_tasks) + 1]

            seen: set[str] = set()
            listings: list[Listing] = []
            for lst in source_lists:
                for l in lst:
                    if l.url not in seen and l.price > 0:
                        seen.add(l.url)
                        listings.append(l)
            total = len(listings)

            await self.emit({"type": "stage", "stage": "distance", "message": f"Calculating distances for {total} listings…"})
            await self._fill_distances(http, geo, listings)

            out_of_radius = 0
            if req.radius:
                kept = []
                for l in listings:
                    if l.is_collection and l.distance_miles is not None and l.distance_miles > req.radius * 1.15:
                        out_of_radius += 1
                    else:
                        kept.append(l)
                listings = kept

            flagged: dict[str, list[str]] = {}
            for l in listings:
                f = red_flags(l.title)
                f += [x for x in red_flags(l.description or "") if x in STRICT_DESC_FLAGS and x not in f]
                flagged[l.id] = f
            flagged_hidden = 0
            if not req.include_flagged:
                flagged_hidden = sum(1 for l in listings if flagged[l.id])
                listings = [l for l in listings if not flagged[l.id]]

            # 2) Deeper per-listing comp lookups where the query-level pool is thin.
            await self.emit({"type": "stage", "stage": "comps", "message": "Matching listings against sold comps & CeX…"})
            thr = self.cfg.match_threshold
            sold_ok = self.statuses.get("ebay_sold") and self.statuses["ebay_sold"].state in ("ok", "cached")
            cex_ok = self.statuses.get("cex") and self.statuses["cex"].state in ("ok", "cached")
            if not self.demo and (sold_ok or cex_ok):
                need_sold: dict[str, None] = {}
                need_cex: dict[str, None] = {}
                for l in listings:
                    cq = comp_query(l.title)
                    if not cq or cq in queries:
                        continue
                    if sold_ok and sold_method == "sold":
                        v = ebay_valuation(l.title, l.condition, sold_pool, thr, base_comps_url)
                        if not v or v.sample_size < 3:
                            need_sold[cq] = None
                    if cex_ok and not best_cex_match(l.title, cex_pool, thr):
                        need_cex[cq] = None
                extra_sold = list(need_sold)[: self.cfg.max_comp_lookups]
                extra_cex = list(need_cex)[: self.cfg.max_comp_lookups]
                if extra_sold or extra_cex:
                    await self.emit({"type": "stage", "stage": "comps", "message": f"Fetching {len(extra_sold)} extra sold searches and {len(extra_cex)} CeX lookups…"})
                    eb, cx = EbayScraper(http), CexClient(http)
                    ttl = self.cfg.comp_cache_ttl_min

                    async def sold_one(q):
                        try:
                            got, cached = await _cached(f"ebay_sold:{q}", ttl, "ebay_sold", lambda: eb.search_sold(q), SoldComp)
                            if not cached:
                                _record_sold(q, got)
                            return got
                        except ScraperError:
                            return []

                    async def cex_one(q):
                        try:
                            return (await _cached(f"cex:{q}", ttl, "cex", lambda: cx.search(q), CexBox))[0]
                        except ScraperError:
                            return []

                    extra = await asyncio.gather(*(sold_one(q) for q in extra_sold), *(cex_one(q) for q in extra_cex))
                    for got in extra[: len(extra_sold)]:
                        sold_pool += got
                    for got in extra[len(extra_sold):]:
                        cex_pool += got

            fb_pool = [l for l in listings if l.source == "facebook"]
            deals: list[Deal] = []
            for l in listings:
                deals.append(self._deal(l, flagged[l.id], sold_pool, sold_method, cex_pool, fb_pool, thr))

            below = 0
            if not req.include_below_threshold:
                below = sum(1 for d in deals if not d.meets_threshold)
                deals = [d for d in deals if d.meets_threshold]
            deals.sort(key=lambda d: (d.best_profit is not None, d.best_profit or 0), reverse=True)

            order = ["ebay", "gumtree", "facebook", "ebay_sold", "cex"]
            statuses = [self.statuses[k] for k in order if k in self.statuses]
            self._annotate_statuses(statuses)

            return SearchResponse(
                query=req.query or (PRESETS.get(req.preset or "", {}).get("label") or ""),
                queries=queries,
                geo=geo,
                radius=req.radius,
                deals=deals,
                statuses=statuses,
                total_listings=total,
                flagged_hidden=flagged_hidden,
                below_threshold_hidden=below,
                out_of_radius_hidden=out_of_radius,
                elapsed_ms=int((time.perf_counter() - t0) * 1000),
            )
        finally:
            await http.aclose()

    def _annotate_statuses(self, statuses: list[SourceStatus]) -> None:
        working = [s.label for s in statuses if s.source in ("ebay", "gumtree", "facebook") and s.state in ("ok", "cached", "demo") and s.count]
        for s in statuses:
            if s.source in ("ebay", "gumtree", "facebook") and s.state in ("login_required", "blocked", "unavailable", "error"):
                tail = f" — showing {' & '.join(working)} results" if working else ""
                if not s.message.endswith(tail):
                    s.message = f"{s.message}{tail}"

    def _deal(
        self,
        l: Listing,
        flags: list[str],
        sold_pool: list[SoldComp],
        sold_method: str,
        cex_pool: list[CexBox],
        fb_pool: list[Listing],
        thr: float,
    ) -> Deal:
        us = self.us
        category = detect_category(l.title)
        buy = P.compute_buy_cost(l.price, l.postage, l.is_collection, l.distance_miles, us)
        ev = ebay_valuation(l.title, l.condition, sold_pool, thr, sold_url(comp_query(l.title) or l.title), sold_method)
        cx = best_cex_match(l.title, cex_pool, thr)
        fv = fb_valuation(l, fb_pool, ev, us, thr)
        exits = [P.ebay_exit(ev, buy, category, us), P.fb_exit(fv, buy), P.cex_exit(cx, buy, us)]
        if ev and ev.method == "active_estimate":
            exits[0].note = f"Estimated from {ev.sample_size} active listings (sold comps unavailable)"
            exits[0].risk = "high"
        best, rf = P.pick_best(exits)
        badge, risk_badge = P.badges(best, rf)
        meets = any(
            e.available and e.profit is not None and e.profit >= self.req.min_profit and (e.roi or 0) >= self.req.min_roi
            for e in exits
        )
        return Deal(
            listing=l,
            normalized_title=normalize_title(l.title),
            category=category,
            flags=flags,
            buy_cost=buy,
            ebay=ev,
            cex=cx,
            fb=fv,
            exits=exits,
            best_exit=best.channel if best else None,
            best_profit=best.profit if best else None,
            best_roi=best.roi if best else None,
            risk_free_profit=rf.profit if rf else None,
            badge=badge,
            risk_badge=risk_badge,
            meets_threshold=meets,
        )


async def run_search(req: SearchRequest, emit: Emit | None = None) -> SearchResponse:
    return await SearchRunner(req, emit).run()
