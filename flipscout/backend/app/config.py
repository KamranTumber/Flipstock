"""Process-level configuration loaded from environment / .env.

User-tunable business settings (fuel cost, fee presets, shipping tiers ...) live in
the database instead (see ``services/user_settings.py``) so they can be edited from
the UI. Values here are infrastructure knobs.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = ""

    # Serve deterministic fixture data from every scraper (offline exploration / demos).
    demo_mode: bool = False

    # Official eBay Browse API (free developer keys from developer.ebay.com). Strongly
    # recommended: eBay frequently refuses automated HTML requests.
    ebay_client_id: str = ""
    ebay_client_secret: str = ""

    # Facebook Marketplace session cookies (optional, from your own logged-in browser).
    fb_c_user: str = ""
    fb_xs: str = ""
    # Marketplace location slug override, e.g. "london" or a numeric FB location id.
    fb_location_slug: str = ""
    # What to do when FB blocks us: "status" = just report it, "demo" = show labelled demo items.
    fb_fallback: Literal["status", "demo"] = "status"

    # Use a headless Chromium (Playwright) when plain HTTP gets an anti-bot page.
    use_playwright: bool = True
    playwright_headless: bool = True

    request_timeout: float = 20.0
    min_request_interval: float = 1.2  # seconds between requests to the same host
    max_retries: int = 2

    listing_cache_ttl_min: int = 15
    comp_cache_ttl_min: int = 360
    geocode_cache_ttl_min: int = 60 * 24 * 30

    max_listings_per_source: int = 40
    max_comp_lookups: int = 8  # per-listing eBay sold lookups when the query-level pool is thin
    match_threshold: int = 72  # rapidfuzz score (0-100) for a comp to count

    # CeX search. The public site uses Algolia; keys are public search-only keys
    # embedded in uk.webuy.com. Override here if CeX rotates them.
    cex_algolia_app_id: str = "LNNFEEWZVX"
    cex_algolia_api_key: str = "bf79f2b6699e60a18ae330a1248b452c"
    cex_algolia_index: str = "prod_cex_uk"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{(DATA_DIR / 'flipscout.db').as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
