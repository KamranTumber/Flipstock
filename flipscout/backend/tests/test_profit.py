import pytest

from app.schemas import CexBox, EbayValuation, FbValuation, UserSettings
from app.services import profit as P


def val(median=200.0, n=10):
    return EbayValuation(median=median, mean=median, low=median, high=median, sample_size=n, comps_url="https://x")


def test_travel_cost_is_round_trip():
    assert P.travel_cost(10, 20) == 4.00
    assert P.travel_cost(None, 20) == 0
    assert P.travel_cost(0, 45) == 0


def test_buy_cost_collection_includes_fuel():
    s = UserSettings(fuel_pence_per_mile=20)
    bc = P.compute_buy_cost(100, None, True, 10, s)
    assert bc.total == 104.00
    assert any("Fuel" in l.label for l in bc.lines)


def test_buy_cost_posted_includes_postage_not_fuel():
    s = UserSettings()
    bc = P.compute_buy_cost(100, 5.99, False, 80, s)
    assert bc.total == 105.99
    assert not any("Fuel" in l.label for l in bc.lines)


def test_ebay_exit_private_seller():
    s = UserSettings(fuel_pence_per_mile=20, ebay_seller_type="private")
    bc = P.compute_buy_cost(100, None, True, 10, s)  # 104
    e = P.ebay_exit(val(200), bc, "console", s)
    # 200 - 0 fee - 6.50 medium postage = 193.50 ; profit 89.50 ; roi 86.1
    assert e.net_proceeds == 193.50
    assert e.profit == 89.50
    assert e.roi == 86.1
    assert e.risk == "low"


def test_ebay_exit_business_fees_and_promoted():
    s = UserSettings(fuel_pence_per_mile=20, ebay_seller_type="business", ebay_promoted_pct=2)
    bc = P.compute_buy_cost(100, None, True, 10, s)
    e = P.ebay_exit(val(200), bc, "console", s)
    # fee 25.60 + 0.30 = 25.90 ; promoted 4.00 ; postage 6.50 -> net 163.60
    assert e.net_proceeds == pytest.approx(163.60)
    assert e.profit == pytest.approx(59.60)


def test_shipping_tiers():
    s = UserSettings()
    assert P.outbound_shipping("audio", 50, s)[0] == 3.50
    assert P.outbound_shipping("gpu", 200, s)[0] == 6.50
    assert P.outbound_shipping("gpu", 400, s)[0] == 11.00  # high value insured


def test_fb_exit_has_no_fees():
    s = UserSettings()
    bc = P.compute_buy_cost(50, None, True, 0, s)
    e = P.fb_exit(FbValuation(value=80, method="heuristic"), bc)
    assert e.profit == 30
    assert e.roi == 60.0
    assert e.risk == "high"


def test_cex_cash_vs_voucher_and_dropoff():
    box = CexBox(box_id="1", name="x", cash=90, voucher=120, retail=200, url="https://cex")
    bc = P.compute_buy_cost(60, 0, False, None, UserSettings())
    cash = P.cex_exit(box, bc, UserSettings(cex_payout="cash"))
    assert cash.profit == 30
    vouch = P.cex_exit(box, bc, UserSettings(cex_payout="voucher", cex_dropoff_miles=5, fuel_pence_per_mile=20))
    assert vouch.profit == 58.0  # 120 - 2.00 travel - 60


def test_unavailable_exits():
    bc = P.compute_buy_cost(10, 0, False, None, UserSettings())
    assert not P.ebay_exit(None, bc, "other", UserSettings()).available
    assert not P.cex_exit(None, bc, UserSettings()).available
    assert not P.fb_exit(None, bc).available


def test_pick_best_and_badges():
    s = UserSettings()
    bc = P.compute_buy_cost(100, 0, False, None, s)
    eb = P.ebay_exit(val(200), bc, "console", s)
    cx = P.cex_exit(CexBox(box_id="1", name="x", cash=140, url="u"), bc, s)
    best, rf = P.pick_best([eb, cx])
    assert best.channel == "ebay"
    assert rf.channel == "cex"
    b, r = P.badges(best, rf)
    assert b == "Best: £94 net on eBay"
    assert r == "Risk-free: £40 instant cash at CeX"


def test_roi_zero_cost():
    assert P.roi_pct(10, 0) is None
