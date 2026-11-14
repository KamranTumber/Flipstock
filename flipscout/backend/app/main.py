"""FastAPI entrypoint: REST + SSE API, and serves the built frontend if present."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from . import __version__
from .config import FRONTEND_DIST, get_settings
from .db import get_session, init_db
from .models import WatchlistItem, utcnow
from .schemas import (
    Deal,
    GeoPoint,
    SearchRequest,
    SearchResponse,
    UserSettings,
    UserSettingsPublic,
    WatchlistCreate,
    WatchlistOut,
    WatchlistUpdate,
)
from .scrapers.browser import browser_pool
from .scrapers.base import Http, ScraperError
from .scrapers.ebay import api_configured, test_connection
from .services.geocode import GeocodeError, geocode_postcode
from .services.search import PRESETS, SearchError, run_search
from .services.user_settings import load_user_settings, public_view, save_user_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("flipscout")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield
    await browser_pool.close()


app = FastAPI(title="FlipScout UK", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- meta


@app.get("/api/health")
def health():
    cfg = get_settings()
    us = load_user_settings()
    return {
        "ok": True,
        "version": __version__,
        "demo_mode": cfg.demo_mode,
        "ebay_api": api_configured(),
        "fb_cookies": bool(us.fb_c_user and us.fb_xs),
        "playwright": cfg.use_playwright,
    }


@app.get("/api/presets")
def presets():
    return [{"id": k, "label": v["label"], "queries": v["queries"]} for k, v in PRESETS.items()]


@app.get("/api/geocode", response_model=GeoPoint)
async def geocode(postcode: str):
    try:
        return await geocode_postcode(postcode)
    except GeocodeError as e:
        raise HTTPException(400, str(e)) from e


# --------------------------------------------------------------------------- search


@app.post("/api/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    try:
        return await run_search(req)
    except SearchError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/search/stream")
async def search_stream(
    request: Request,
    postcode: str,
    q: str = "",
    preset: Optional[str] = None,
    radius: int = 25,
    min_profit: float = 0,
    min_roi: float = 0,
    sources: str = "ebay,gumtree,facebook",
    include_flagged: bool = False,
    include_below_threshold: bool = False,
    demo: bool = False,
):
    """Server-Sent Events: progress events, then a final {type: 'result'} event."""
    try:
        req = SearchRequest(
            query=q,
            preset=preset or None,
            postcode=postcode,
            radius=radius,
            min_profit=min_profit,
            min_roi=min_roi,
            sources=[s for s in sources.split(",") if s in ("ebay", "gumtree", "facebook")],
            include_flagged=include_flagged,
            include_below_threshold=include_below_threshold,
            demo=demo,
        )
    except Exception as e:
        raise HTTPException(422, str(e)) from e

    queue: asyncio.Queue = asyncio.Queue()

    async def emit(evt: dict) -> None:
        await queue.put(evt)

    async def runner():
        try:
            res = await run_search(req, emit)
            await queue.put({"type": "result", "data": res.model_dump(mode="json")})
        except SearchError as e:
            await queue.put({"type": "error", "message": str(e)})
        except Exception as e:  # never kill the stream silently
            log.exception("search failed")
            await queue.put({"type": "error", "message": f"Search failed: {e.__class__.__name__}: {e}"})
        finally:
            await queue.put(None)

    task = asyncio.create_task(runner())

    async def gen():
        try:
            yield "retry: 0\n\n"
            while True:
                try:
                    evt = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    if await request.is_disconnected():
                        break
                    continue
                if evt is None:
                    yield "event: done\ndata: {}\n\n"
                    break
                yield f"data: {json.dumps(evt, default=str)}\n\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


# --------------------------------------------------------------------------- settings


@app.post("/api/ebay/test")
async def ebay_test():
    """Checks the saved eBay API keys: gets an OAuth token and runs one tiny search."""
    if not api_configured():
        return {"ok": False, "message": "No eBay API keys saved yet."}
    http = Http()
    try:
        return await test_connection(http)
    except ScraperError as e:
        return {"ok": False, "message": str(e)}
    finally:
        await http.aclose()


@app.get("/api/settings", response_model=UserSettingsPublic)
def get_user_settings():
    return public_view(load_user_settings())


@app.put("/api/settings", response_model=UserSettingsPublic)
def put_user_settings(body: UserSettings):
    return public_view(save_user_settings(body))


# --------------------------------------------------------------------------- watchlist


def _wl_out(row: WatchlistItem) -> WatchlistOut:
    deal = None
    try:
        deal = Deal(**json.loads(row.snapshot)) if row.snapshot and row.snapshot != "{}" else None
    except Exception:
        deal = None
    realised = None
    if row.actual_sale_price is not None:
        realised = round(row.actual_sale_price - (row.actual_buy_price if row.actual_buy_price is not None else row.buy_price), 2)
    return WatchlistOut(
        id=row.id,  # type: ignore[arg-type]
        listing_id=row.listing_id,
        source=row.source,
        title=row.title,
        url=row.url,
        image_url=row.image_url,
        buy_price=row.buy_price,
        best_channel=row.best_channel,
        best_profit=row.best_profit,
        status=row.status,
        notes=row.notes,
        actual_buy_price=row.actual_buy_price,
        actual_sale_price=row.actual_sale_price,
        realised_profit=realised,
        deal=deal,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


@app.get("/api/watchlist", response_model=list[WatchlistOut])
def list_watchlist(status: Optional[str] = Query(None), s: Session = Depends(get_session)):
    stmt = select(WatchlistItem).order_by(WatchlistItem.updated_at.desc())  # type: ignore[attr-defined]
    if status:
        stmt = stmt.where(WatchlistItem.status == status)
    return [_wl_out(r) for r in s.exec(stmt).all()]


@app.post("/api/watchlist", response_model=WatchlistOut, status_code=201)
def add_watchlist(body: WatchlistCreate, s: Session = Depends(get_session)):
    d = body.deal
    row = s.exec(select(WatchlistItem).where(WatchlistItem.listing_id == d.listing.id)).first()
    if row is None:
        row = WatchlistItem(listing_id=d.listing.id, source=d.listing.source, title=d.listing.title, url=d.listing.url, buy_price=d.listing.price)
    row.image_url = d.listing.image_url
    row.best_channel = d.best_exit
    row.best_profit = d.best_profit
    row.snapshot = d.model_dump_json()
    if body.notes:
        row.notes = body.notes
    row.updated_at = utcnow()
    s.add(row)
    s.commit()
    s.refresh(row)
    return _wl_out(row)


@app.patch("/api/watchlist/{item_id}", response_model=WatchlistOut)
def update_watchlist(item_id: int, body: WatchlistUpdate, s: Session = Depends(get_session)):
    row = s.get(WatchlistItem, item_id)
    if not row:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    row.updated_at = utcnow()
    s.add(row)
    s.commit()
    s.refresh(row)
    return _wl_out(row)


@app.delete("/api/watchlist/{item_id}", status_code=204)
def delete_watchlist(item_id: int, s: Session = Depends(get_session)):
    row = s.get(WatchlistItem, item_id)
    if not row:
        raise HTTPException(404, "Not found")
    s.delete(row)
    s.commit()


# --------------------------------------------------------------------------- SPA

if (FRONTEND_DIST / "index.html").exists():
    if (FRONTEND_DIST / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = FRONTEND_DIST / path
        if path and f.is_file() and FRONTEND_DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(FRONTEND_DIST / "index.html")
