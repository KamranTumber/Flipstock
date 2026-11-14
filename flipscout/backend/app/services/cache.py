"""Tiny JSON cache on top of SQLite so repeat searches are instant."""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any

from ..db import session_scope
from ..models import ScrapeCache, age, utcnow

log = logging.getLogger(__name__)


def cache_get(key: str, ttl_minutes: int) -> Any | None:
    try:
        with session_scope() as s:
            row = s.get(ScrapeCache, key)
            if row is None:
                return None
            if age(row.fetched_at) > timedelta(minutes=ttl_minutes):
                return None
            return json.loads(row.payload)
    except Exception:  # cache must never break a search
        log.exception("cache_get failed for %s", key)
        return None


def cache_set(key: str, source: str, payload: Any) -> None:
    try:
        with session_scope() as s:
            row = s.get(ScrapeCache, key)
            data = json.dumps(payload, default=str)
            if row is None:
                row = ScrapeCache(key=key, source=source, payload=data)
            else:
                row.payload = data
                row.fetched_at = utcnow()
            s.add(row)
            s.commit()
    except Exception:
        log.exception("cache_set failed for %s", key)
