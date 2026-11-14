"""Pydantic API / domain models shared between scrapers, services and routes."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

SourceName = Literal["ebay", "gumtree", "facebook"]
ExitName = Literal["ebay", "facebook", "cex"]
SourceState = Literal["ok", "cached", "blocked", "login_required", "error", "unavailable", "disabled", "demo"]


class GeoPoint(BaseModel):
    postcode: str
    outcode: str
    latitude: float
    longitude: float
    district: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None


class Listing(BaseModel):
    id: str
    source: SourceName
    title: str
    price: float
    postage: Optional[float] = None  # None = unknown / collection only
    condition: Optional[str] = None
    listing_type: Literal["buy_it_now", "auction", "classified"] = "classified"
    bids: Optional[int] = None
    time_left: Optional[str] = None
    seller_feedback: Optional[str] = None
    location: Optional[str] = None
    distance_miles: Optional[float] = None
    image_url: Optional[str] = None
    url: str
    posted_at: Optional[str] = None
    description: Optional[str] = None
    is_collection: bool = False
    is_demo: bool = False


class SoldComp(BaseModel):
    title: str
    price: float
    shipping: Optional[float] = None
    condition: Optional[str] = None
    sold_date: Optional[str] = None
    url: str
    image_url: Optional[str] = None
    match_score: Optional[float] = None


class CexBox(BaseModel):
    box_id: str
    name: str
    category: Optional[str] = None
    cash: Optional[float] = None
    voucher: Optional[float] = None
    retail: Optional[float] = None
    image_url: Optional[str] = None
    url: str
    match_score: Optional[float] = None


class EbayValuation(BaseModel):
    median: float
    mean: float
    low: float
    high: float
    avg_shipping: Optional[float] = None
    sample_size: int
    method: Literal["sold", "active_estimate"] = "sold"
    comps_url: str
    comps: list[SoldComp] = Field(default_factory=list)


class FbValuation(BaseModel):
    value: float
    method: Literal["active_comps", "heuristic"]
    sample_size: int = 0
    note: str = ""


class CostLine(BaseModel):
    label: str
    amount: float  # positive = money in, negative = money out


class BuyCost(BaseModel):
    lines: list[CostLine]
    total: float


class ExitChannel(BaseModel):
    channel: ExitName
    label: str
    available: bool
    sale_price: Optional[float] = None
    lines: list[CostLine] = Field(default_factory=list)
    net_proceeds: Optional[float] = None
    profit: Optional[float] = None
    roi: Optional[float] = None
    risk: Literal["low", "medium", "high"] = "medium"
    note: str = ""
    link: Optional[str] = None


class Deal(BaseModel):
    listing: Listing
    normalized_title: str
    category: str
    flags: list[str] = Field(default_factory=list)
    buy_cost: BuyCost
    ebay: Optional[EbayValuation] = None
    cex: Optional[CexBox] = None
    fb: Optional[FbValuation] = None
    exits: list[ExitChannel]
    best_exit: Optional[ExitName] = None
    best_profit: Optional[float] = None
    best_roi: Optional[float] = None
    risk_free_profit: Optional[float] = None  # CeX instant cash profit, when positive
    badge: Optional[str] = None
    risk_badge: Optional[str] = None
    meets_threshold: bool = False


class SourceStatus(BaseModel):
    source: str
    label: str
    state: SourceState
    message: str = ""
    count: int = 0
    elapsed_ms: int = 0


class SearchRequest(BaseModel):
    query: str = ""
    preset: Optional[str] = None
    postcode: str
    radius: int = 25  # miles; 0 = nationwide
    min_profit: float = 0
    min_roi: float = 0
    sources: list[SourceName] = Field(default_factory=lambda: ["ebay", "gumtree", "facebook"])
    include_flagged: bool = False
    include_below_threshold: bool = False
    demo: bool = False


class SearchResponse(BaseModel):
    query: str
    queries: list[str]
    geo: GeoPoint
    radius: int
    deals: list[Deal]
    statuses: list[SourceStatus]
    total_listings: int
    flagged_hidden: int
    below_threshold_hidden: int
    out_of_radius_hidden: int
    elapsed_ms: int


class UserSettings(BaseModel):
    """Editable from the Settings panel; persisted in SQLite."""

    default_postcode: str = ""
    default_radius: int = 25
    default_min_profit: float = 20
    default_min_roi: float = 15

    fuel_pence_per_mile: float = 20.0  # fuel only; HMRC 45p covers full running cost

    ship_small: float = 3.50
    ship_medium: float = 6.50
    ship_high_value: float = 11.00
    high_value_threshold: float = 250.0

    ebay_seller_type: Literal["private", "business"] = "private"
    ebay_business_fee_pct: float = 12.8
    ebay_business_fixed_fee: float = 0.30
    ebay_private_fee_pct: float = 0.0
    ebay_promoted_pct: float = 0.0

    fb_local_factor: float = 0.90  # heuristic: FB local cash value vs eBay sold median
    fb_active_discount: float = 0.92  # active asking prices are usually negotiated down

    cex_payout: Literal["cash", "voucher"] = "cash"
    cex_dropoff_miles: float = 0.0  # one-way miles to your nearest CeX store

    fb_c_user: str = ""
    fb_xs: str = ""

    ebay_client_id: str = ""  # eBay developer "App ID" (Production)
    ebay_client_secret: str = ""  # eBay developer "Cert ID" (Production)


class UserSettingsPublic(UserSettings):
    """Same as UserSettings but secrets masked for display."""

    fb_cookie_configured: bool = False
    ebay_api_configured: bool = False


class WatchlistCreate(BaseModel):
    deal: Deal
    notes: str = ""


class WatchlistUpdate(BaseModel):
    status: Optional[Literal["watching", "purchased", "listed", "sold"]] = None
    notes: Optional[str] = None
    actual_buy_price: Optional[float] = None
    actual_sale_price: Optional[float] = None


class WatchlistOut(BaseModel):
    id: int
    listing_id: str
    source: str
    title: str
    url: str
    image_url: Optional[str]
    buy_price: float
    best_channel: Optional[str]
    best_profit: Optional[float]
    status: str
    notes: str
    actual_buy_price: Optional[float]
    actual_sale_price: Optional[float]
    realised_profit: Optional[float]
    deal: Optional[Deal]
    created_at: str
    updated_at: str
