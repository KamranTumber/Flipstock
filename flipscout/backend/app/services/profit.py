"""Pure, side-effect-free profit & cost breakdown engine.

Sign convention for CostLine.amount: positive = money in, negative = money out.
ROI = profit / total buy cost * 100.
"""

from __future__ import annotations

from typing import Optional

from ..schemas import BuyCost, CexBox, CostLine, EbayValuation, ExitChannel, FbValuation, UserSettings
from .normalizer import SMALL_CATEGORIES


def money(x: float) -> float:
    return round(float(x) + 0.0, 2)


def roi_pct(profit: float, cost: float) -> Optional[float]:
    if cost <= 0:
        return None
    return round(profit / cost * 100, 1)


def travel_cost(one_way_miles: Optional[float], pence_per_mile: float) -> float:
    """Round-trip fuel cost in £."""
    if not one_way_miles or one_way_miles <= 0:
        return 0.0
    return money(one_way_miles * 2 * pence_per_mile / 100)


def compute_buy_cost(
    price: float,
    postage: Optional[float],
    is_collection: bool,
    distance_miles: Optional[float],
    s: UserSettings,
) -> BuyCost:
    lines = [CostLine(label="Purchase price", amount=-money(price))]
    if is_collection:
        tc = travel_cost(distance_miles, s.fuel_pence_per_mile)
        if distance_miles:
            label = f"Fuel: {distance_miles:.1f} mi × 2 @ {s.fuel_pence_per_mile:g}p/mi"
        else:
            label = "Fuel (distance unknown)"
        lines.append(CostLine(label=label, amount=-tc))
    else:
        lines.append(CostLine(label="Inbound postage", amount=-money(postage or 0)))
    total = money(-sum(l.amount for l in lines))
    return BuyCost(lines=lines, total=total)


def outbound_shipping(category: str, sale_price: float, s: UserSettings) -> tuple[float, str]:
    if sale_price >= s.high_value_threshold:
        return s.ship_high_value, "Insured tracked postage (high value)"
    if category in SMALL_CATEGORIES:
        return s.ship_small, "Tracked postage (small parcel)"
    return s.ship_medium, "Tracked postage (medium parcel)"


def ebay_fees(sale_price: float, s: UserSettings) -> list[CostLine]:
    lines: list[CostLine] = []
    if s.ebay_seller_type == "business":
        fee = sale_price * s.ebay_business_fee_pct / 100 + s.ebay_business_fixed_fee
        lines.append(
            CostLine(
                label=f"eBay final value fee ({s.ebay_business_fee_pct:g}% + £{s.ebay_business_fixed_fee:.2f})",
                amount=-money(fee),
            )
        )
    else:
        fee = sale_price * s.ebay_private_fee_pct / 100
        lines.append(CostLine(label=f"eBay private seller fee ({s.ebay_private_fee_pct:g}%)", amount=-money(fee)))
    if s.ebay_promoted_pct > 0:
        lines.append(
            CostLine(label=f"Promoted listing ({s.ebay_promoted_pct:g}%)", amount=-money(sale_price * s.ebay_promoted_pct / 100))
        )
    return lines


def _finish(exit_: ExitChannel, buy: BuyCost) -> ExitChannel:
    net = money(sum(l.amount for l in exit_.lines))
    exit_.net_proceeds = net
    exit_.profit = money(net - buy.total)
    exit_.roi = roi_pct(exit_.profit, buy.total)
    return exit_


def ebay_exit(val: Optional[EbayValuation], buy: BuyCost, category: str, s: UserSettings) -> ExitChannel:
    if not val:
        return ExitChannel(channel="ebay", label="Flip on eBay UK", available=False, note="No matching sold comps found")
    sale = val.median
    ship, ship_label = outbound_shipping(category, sale, s)
    lines = [CostLine(label=f"eBay sold median ({val.sample_size} sales)", amount=money(sale))]
    lines += ebay_fees(sale, s)
    lines.append(CostLine(label=ship_label, amount=-money(ship)))
    risk = "low" if val.sample_size >= 8 else "medium" if val.sample_size >= 3 else "high"
    return _finish(
        ExitChannel(
            channel="ebay",
            label="Flip on eBay UK",
            available=True,
            sale_price=money(sale),
            lines=lines,
            risk=risk,
            note=f"Based on {val.sample_size} recent sale{'s' if val.sample_size != 1 else ''}",
            link=val.comps_url,
        ),
        buy,
    )


def fb_exit(val: Optional[FbValuation], buy: BuyCost) -> ExitChannel:
    if not val:
        return ExitChannel(channel="facebook", label="Sell on FB Marketplace", available=False, note="No local value estimate")
    lines = [
        CostLine(
            label="Expected local cash sale" + (" (est.)" if val.method == "heuristic" else ""),
            amount=money(val.value),
        ),
        CostLine(label="Selling fees (cash on collection)", amount=0.0),
        CostLine(label="Outbound postage (buyer collects)", amount=0.0),
    ]
    return _finish(
        ExitChannel(
            channel="facebook",
            label="Sell on FB Marketplace",
            available=True,
            sale_price=money(val.value),
            lines=lines,
            risk="medium" if val.method == "active_comps" else "high",
            note=val.note,
        ),
        buy,
    )


def cex_exit(box: Optional[CexBox], buy: BuyCost, s: UserSettings) -> ExitChannel:
    payout = None
    if box:
        payout = box.voucher if s.cex_payout == "voucher" else box.cash
    if not box or payout is None:
        return ExitChannel(channel="cex", label="Instant cash at CeX", available=False, note="No CeX trade-in match")
    kind = "voucher" if s.cex_payout == "voucher" else "cash"
    lines = [
        CostLine(label=f"CeX {kind} trade-in offer", amount=money(payout)),
        CostLine(label="CeX fees", amount=0.0),
    ]
    if s.cex_dropoff_miles > 0:
        lines.append(
            CostLine(
                label=f"Drop-off fuel: {s.cex_dropoff_miles:g} mi × 2 @ {s.fuel_pence_per_mile:g}p/mi",
                amount=-travel_cost(s.cex_dropoff_miles, s.fuel_pence_per_mile),
            )
        )
    return _finish(
        ExitChannel(
            channel="cex",
            label="Instant cash at CeX" if kind == "cash" else "CeX voucher trade-in",
            available=True,
            sale_price=money(payout),
            lines=lines,
            risk="low",
            note=f"Guaranteed {kind} price (subject to CeX testing/grade)",
            link=box.url,
        ),
        buy,
    )


CHANNEL_NAMES = {"ebay": "eBay", "facebook": "FB Marketplace", "cex": "CeX"}


def pick_best(exits: list[ExitChannel]) -> tuple[Optional[ExitChannel], Optional[ExitChannel]]:
    """Return (highest-profit exit, low-risk CeX exit if it is profitable)."""
    avail = [e for e in exits if e.available and e.profit is not None]
    if not avail:
        return None, None
    best = max(avail, key=lambda e: (e.profit, e.risk == "low"))
    cex = next((e for e in avail if e.channel == "cex" and (e.profit or 0) > 0), None)
    return best, cex


def badges(best: Optional[ExitChannel], risk_free: Optional[ExitChannel]) -> tuple[Optional[str], Optional[str]]:
    badge = None
    if best is not None:
        if (best.profit or 0) > 0:
            badge = f"Best: £{best.profit:,.0f} net on {CHANNEL_NAMES[best.channel]}"
        else:
            badge = f"No profitable exit (best {CHANNEL_NAMES[best.channel]}: −£{abs(best.profit or 0):,.0f})"
    rb = None
    if risk_free is not None:
        kind = "voucher" if "voucher" in risk_free.label.lower() else "instant cash"
        rb = f"Risk-free: £{risk_free.profit:,.0f} {kind} at CeX"
    return badge, rb
