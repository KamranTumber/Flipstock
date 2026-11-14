"""SQLite tables."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def age(ts: datetime):
    """Time since ``ts`` (tolerates naive timestamps read back from SQLite)."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return utcnow() - ts


class ScrapeCache(SQLModel, table=True):
    """Generic JSON cache for scraper responses (listings, comps, CeX boxes)."""

    key: str = Field(primary_key=True)
    source: str = Field(index=True)
    payload: str
    fetched_at: datetime = Field(default_factory=utcnow, index=True)


class GeoCache(SQLModel, table=True):
    key: str = Field(primary_key=True)  # "pc:RH191AA" / "place:crawley"
    payload: str
    fetched_at: datetime = Field(default_factory=utcnow)


class SoldPrice(SQLModel, table=True):
    """Historical eBay sold prices, kept to build a price history over time."""

    id: Optional[int] = Field(default=None, primary_key=True)
    comp_query: str = Field(index=True)
    title: str
    price: float
    shipping: Optional[float] = None
    condition: Optional[str] = None
    sold_date: Optional[str] = None
    url: str = Field(index=True, unique=True)
    recorded_at: datetime = Field(default_factory=utcnow)


class WatchlistItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: str = Field(index=True, unique=True)
    source: str
    title: str
    url: str
    image_url: Optional[str] = None
    buy_price: float
    best_channel: Optional[str] = None
    best_profit: Optional[float] = None
    status: str = Field(default="watching")  # watching | purchased | listed | sold
    notes: str = ""
    actual_buy_price: Optional[float] = None
    actual_sale_price: Optional[float] = None
    snapshot: str = "{}"  # full Deal JSON at time of saving
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class AppSettingsRow(SQLModel, table=True):
    id: int = Field(default=1, primary_key=True)
    data: str = "{}"
    updated_at: datetime = Field(default_factory=utcnow)
