"""End-to-end API tests in demo mode with geocoding stubbed (no network)."""

import json

import pytest
from fastapi.testclient import TestClient

from app.schemas import GeoPoint

GEO = GeoPoint(postcode="RH19 1AA", outcode="RH19", latitude=51.1259, longitude=-0.0097, district="Mid Sussex")


@pytest.fixture
def client(monkeypatch):
    from app import main
    from app.services import search

    async def fake_geocode(pc, client=None):
        return GEO

    async def fake_place(text, client, near=None):
        return None

    monkeypatch.setattr(search, "geocode_postcode", fake_geocode)
    monkeypatch.setattr(search, "geocode_place", fake_place)
    with TestClient(main.app) as c:
        yield c


def test_health_and_presets(client):
    assert client.get("/api/health").json()["ok"] is True
    ids = {p["id"] for p in client.get("/api/presets").json()}
    assert {"gpus", "apple", "consoles", "audio"} <= ids


def test_demo_search_returns_itemised_deals(client):
    r = client.post("/api/search", json={"query": "ps5", "postcode": "RH19 1AA", "radius": 25, "demo": True, "include_below_threshold": True})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["deals"], data
    states = {s["source"]: s["state"] for s in data["statuses"]}
    assert states["ebay"] == "demo" and states["cex"] == "demo"
    d = data["deals"][0]
    assert {e["channel"] for e in d["exits"]} == {"ebay", "facebook", "cex"}
    assert d["buy_cost"]["lines"] and d["listing"]["is_demo"]
    # red-flag demo items (spares / box only / icloud) are hidden by default
    assert all(not x["flags"] for x in data["deals"])


def test_flagged_included_when_requested(client):
    r = client.post(
        "/api/search",
        json={"preset": "consoles", "postcode": "RH19 1AA", "demo": True, "include_flagged": True, "include_below_threshold": True},
    )
    assert r.status_code == 200
    assert r.json()["flagged_hidden"] == 0


def test_empty_query_is_400(client):
    r = client.post("/api/search", json={"query": "", "postcode": "RH19 1AA"})
    assert r.status_code == 400


def test_sse_stream(client):
    with client.stream("GET", "/api/search/stream", params={"q": "rtx 3080", "postcode": "RH19 1AA", "demo": "true"}) as r:
        events = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ") and line != "data: {}"]
    types = [e["type"] for e in events]
    assert "stage" in types and "source" in types and types[-1] == "result"


def test_watchlist_crud(client):
    data = client.post("/api/search", json={"query": "iphone 13", "postcode": "RH19 1AA", "demo": True, "include_below_threshold": True}).json()
    deal = data["deals"][0]
    created = client.post("/api/watchlist", json={"deal": deal, "notes": "check battery"}).json()
    assert created["status"] == "watching"
    upd = client.patch(f"/api/watchlist/{created['id']}", json={"status": "sold", "actual_sale_price": deal["listing"]["price"] + 50}).json()
    assert upd["status"] == "sold" and upd["realised_profit"] == 50
    assert len(client.get("/api/watchlist").json()) == 1
    assert client.delete(f"/api/watchlist/{created['id']}").status_code == 204


def test_ebay_keys_in_settings_and_test_endpoint(client, monkeypatch):
    from app.scrapers import ebay
    from app.schemas import Listing

    assert client.post("/api/ebay/test").json()["ok"] is False  # nothing saved yet

    s = client.get("/api/settings").json()
    s.update({"ebay_client_id": " Me-FlipScou-PRD-abc ", "ebay_client_secret": "PRD-secret"})
    out = client.put("/api/settings", json=s).json()
    assert out["ebay_api_configured"] and out["ebay_client_secret"] != "PRD-secret"
    assert out["ebay_client_id"] == "Me-FlipScou-PRD-abc"  # whitespace trimmed
    assert ebay.ebay_credentials() == ("Me-FlipScou-PRD-abc", "PRD-secret")
    assert client.get("/api/health").json()["ebay_api"] is True

    async def fake_search(http, query, geo, mode, limit, radius=0, local_only=False):
        return [Listing(id="ebay:1", source="ebay", title="PS5", price=300, url="https://www.ebay.co.uk/itm/1")]

    monkeypatch.setattr(ebay, "api_search", fake_search)
    r = client.post("/api/ebay/test").json()
    assert r["ok"] and r["sample"][0]["price"] == 300


def test_settings_masks_cookies(client):
    s = client.get("/api/settings").json()
    s.update({"fuel_pence_per_mile": 30, "fb_c_user": "123", "fb_xs": "secret"})
    out = client.put("/api/settings", json=s).json()
    assert out["fuel_pence_per_mile"] == 30
    assert out["fb_cookie_configured"] and out["fb_xs"] != "secret"
    # sending the mask back keeps the stored value
    out2 = client.put("/api/settings", json=out).json()
    assert out2["fb_cookie_configured"]
