"""UK postcode / place geocoding via the free postcodes.io API."""

from __future__ import annotations

import json
import math
import re
from datetime import timedelta

import httpx

from ..config import get_settings
from ..db import session_scope
from ..models import GeoCache, age, utcnow
from ..schemas import GeoPoint

API = "https://api.postcodes.io"

POSTCODE_RE = re.compile(r"^([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})$")
OUTCODE_RE = re.compile(r"^[A-Z]{1,2}\d[A-Z\d]?$")


class GeocodeError(Exception):
    pass


def clean_postcode(raw: str) -> str:
    pc = re.sub(r"[^A-Za-z0-9]", "", raw or "").upper()
    m = POSTCODE_RE.match(pc)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return pc


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _cache_read(key: str) -> dict | None:
    ttl = get_settings().geocode_cache_ttl_min
    with session_scope() as s:
        row = s.get(GeoCache, key)
        if row and age(row.fetched_at) < timedelta(minutes=ttl):
            return json.loads(row.payload)
    return None


def _cache_write(key: str, payload: dict) -> None:
    with session_scope() as s:
        row = s.get(GeoCache, key) or GeoCache(key=key, payload="")
        row.payload = json.dumps(payload)
        row.fetched_at = utcnow()
        s.add(row)
        s.commit()


async def geocode_postcode(raw: str, client: httpx.AsyncClient | None = None) -> GeoPoint:
    pc = clean_postcode(raw)
    if not pc:
        raise GeocodeError("Please enter a UK postcode.")
    key = f"pc:{pc.replace(' ', '')}"
    cached = _cache_read(key)
    if cached:
        return GeoPoint(**cached)

    own = client is None
    client = client or httpx.AsyncClient(timeout=10)
    try:
        if POSTCODE_RE.match(pc.replace(" ", "")):
            r = await client.get(f"{API}/postcodes/{pc.replace(' ', '')}")
            if r.status_code == 200:
                res = r.json()["result"]
                geo = GeoPoint(
                    postcode=res["postcode"],
                    outcode=res["outcode"],
                    latitude=res["latitude"],
                    longitude=res["longitude"],
                    district=res.get("admin_district"),
                    region=res.get("region"),
                    country=res.get("country"),
                )
                _cache_write(key, geo.model_dump())
                return geo
            if r.status_code != 404:
                raise GeocodeError(f"postcodes.io returned HTTP {r.status_code}")
            # Unknown full postcode (e.g. terminated) -> fall back to its outcode.
            pc = POSTCODE_RE.match(pc.replace(" ", "")).group(1)  # type: ignore[union-attr]

        if OUTCODE_RE.match(pc):
            r = await client.get(f"{API}/outcodes/{pc}")
            if r.status_code == 200:
                res = r.json()["result"]
                district = (res.get("admin_district") or [None])[0]
                geo = GeoPoint(
                    postcode=pc,
                    outcode=res["outcode"],
                    latitude=res["latitude"],
                    longitude=res["longitude"],
                    district=district,
                    region=(res.get("region") or [None])[0] if isinstance(res.get("region"), list) else None,
                    country=(res.get("country") or [None])[0],
                )
                _cache_write(key, geo.model_dump())
                return geo
        raise GeocodeError(f"'{raw}' is not a recognised UK postcode.")
    except httpx.HTTPError as e:
        raise GeocodeError(f"Could not reach postcodes.io: {e.__class__.__name__}") from e
    finally:
        if own:
            await client.aclose()


TYPE_RANK = {"City": 0, "Town": 1, "Village": 2, "Suburban Area": 3, "Hamlet": 4, "Other Settlement": 5}


def pick_place(
    candidates: list[dict], place: str, hint: str = "", near: tuple[float, float] | None = None
) -> tuple[float, float] | None:
    """Choose among same-named places (there are three 'Guildford's): county hint > settlement size > proximity."""
    exact = [c for c in candidates if (c.get("name_1") or "").lower() == place.lower() and c.get("latitude") is not None]
    pool = exact or [c for c in candidates if c.get("latitude") is not None]
    if not pool:
        return None
    hint = hint.lower()

    def rank(c: dict):
        area = " ".join(str(c.get(k) or "") for k in ("county_unitary", "district_borough", "region", "country")).lower()
        hinted = 0 if hint and any(w in area for w in re.split(r"[\s,]+", hint) if len(w) > 3) else 1
        dist = haversine_miles(near[0], near[1], c["latitude"], c["longitude"]) if near else 0
        return (hinted, TYPE_RANK.get(c.get("local_type"), 6), dist)

    best = min(pool, key=rank)
    return best["latitude"], best["longitude"]


async def geocode_place(
    text: str, client: httpx.AsyncClient, near: tuple[float, float] | None = None
) -> tuple[float, float] | None:
    """Best-effort lat/lng for a free-text UK location like 'Crawley, West Sussex' or 'RH10'."""
    if not text:
        return None
    t = text.strip()
    compact = re.sub(r"[^A-Za-z0-9]", "", t).upper()
    if POSTCODE_RE.match(compact) or OUTCODE_RE.match(compact):
        try:
            g = await geocode_postcode(compact, client)
            return g.latitude, g.longitude
        except GeocodeError:
            return None

    parts = re.split(r"[,|•(]", t)
    place = parts[0].strip()
    hint = " ".join(p.strip() for p in parts[1:])
    if not place or len(place) < 3:
        return None
    key = f"places:{place.lower()}"
    cached = _cache_read(key)
    if cached is None:
        try:
            r = await client.get(f"{API}/places", params={"q": place, "limit": 15})
            hits = (r.json().get("result") or []) if r.status_code == 200 else []
        except (httpx.HTTPError, ValueError):
            return None
        keep = ("name_1", "local_type", "county_unitary", "district_borough", "region", "country", "latitude", "longitude")
        cached = {"candidates": [{k: h.get(k) for k in keep} for h in hits]}
        _cache_write(key, cached)
    return pick_place(cached["candidates"], place, hint, near)
