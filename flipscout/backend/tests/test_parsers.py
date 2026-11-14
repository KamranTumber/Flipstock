"""Parser tests against small fixtures that mirror each site's real markup."""

from app.scrapers.cex import hit_to_box
from app.scrapers.ebay import active_url, clean_item_url, parse_search_html, sold_url
from app.scrapers.facebook import parse_marketplace_html, session_cookies
from app.scrapers.gumtree import parse_results, search_url
from app.scrapers.base import parse_distance, parse_price

EBAY_S_ITEM = """
<ul class="srp-results">
 <li class="s-item"><div class="s-item__title">Shop on eBay</div><span class="s-item__price">£20.00</span>
   <a class="s-item__link" href="https://ebay.com/itm/123456"></a></li>
 <li class="s-item">
   <img src="https://i.ebayimg.com/images/g/abc/s-l225.jpg"/>
   <a class="s-item__link" href="https://www.ebay.co.uk/itm/2345678901?hash=item&amp;var=1"><div class="s-item__title"><span>New listing</span>Sony PS5 Disc Console 825GB</div></a>
   <div class="s-item__subtitle"><span class="SECONDARY_INFO">Pre-owned</span></div>
   <span class="s-item__price">£329.99</span>
   <span class="s-item__shipping s-item__logisticsCost">+£6.99 postage</span>
   <span class="s-item__location s-item__itemLocation">from Crawley, United Kingdom</span>
   <span class="s-item__seller-info-text">gamerguy (1,234) 99.8%</span>
   <span class="s-item__bids s-item__bidCount">3 bids</span>
   <span class="s-item__time-left">1d 4h left</span>
 </li>
 <li class="s-item">
   <a class="s-item__link" href="https://www.ebay.co.uk/itm/3456789012"><div class="s-item__title">PS5 Controller</div></a>
   <span class="s-item__price">£30.00 to £45.00</span>
 </li>
</ul>"""

EBAY_S_CARD_SOLD = """
<ul class="srp-results">
 <li class="s-card">
   <a class="su-link" href="https://www.ebay.co.uk/itm/sony-ps5/4567890123?_skw=ps5"><div class="s-card__title"><span>Sony PlayStation 5 Console Disc</span></div></a>
   <div class="s-card__caption">Sold  12 Nov 2026</div>
   <div class="s-card__subtitle">Pre-owned · Sony</div>
   <span class="s-card__price">£310.00</span>
   <div class="s-card__attribute-row">Free postage</div>
   <div class="s-card__attribute-row">from United Kingdom</div>
   <img data-src="https://i.ebayimg.com/x.jpg" src="data:image/gif;base64,AAAA"/>
 </li>
</ul>"""

GUMTREE = """
<div data-q="search-result"><a data-q="search-result-anchor" href="/p/ps5/sony-ps5-slim/1802302551">
 <img alt="x" src="https://img.gumtree.com/a/86"/>
 <h2 data-q="tile-title">Sony PS5 Slim Console with Black Controller</h2>
 <p data-q="tile-description">Fully working</p>
 <div data-q="tile-location">Bromley, London</div>
 <div data-q="tile-price"><span>£</span><span>400</span></div></a></div>
<div data-q="search-result"><a data-q="search-result-anchor" href="/p/ps5/swap/1">
 <h2 data-q="tile-title">PS5 swap for xbox</h2><div data-q="tile-location">Leeds</div></a></div>
<div data-q="search-result"><a data-q="search-result-anchor" href="/p/ps5/lazy/2">
 <img class="lazyload" data-src="https://img.gumtree.com/b/86"/>
 <h2 data-q="tile-title">PS5 Digital</h2><div data-q="tile-location">Crawley, West Sussex | 3 miles</div>
 <div data-q="tile-price">£1,250</div></a></div>
"""

FB = """
<div><a href="/marketplace/item/111222333/?ref=search"><img src="https://scontent.xx/img.jpg"/>
 <span>£250</span><span>£300</span><span>PS5 Disc Edition</span><span>Crawley, West Sussex</span></a>
<a href="/marketplace/item/111222333/">dup</a>
<a href="/marketplace/item/444/"><span>Free</span><span>Old TV</span></a>
<a href="/marketplace/item/555/"><span>£80</span><span>Nintendo Switch Lite</span><span>Horsham</span></a></div>
"""


def test_price_and_distance_helpers():
    assert parse_price("£1,299.99") == 1299.99
    assert parse_price("£ | 400") == 400
    assert parse_price("free") is None
    assert parse_distance("Crawley | 3.5 miles") == 3.5
    assert parse_distance("10 km away") == 6.2


def test_ebay_urls():
    u = active_url("ps5 console", "RH19 1AA", "bin")
    assert "LH_PrefLoc=1" in u and "LH_BIN=1" in u and "_stpos=RH191AA" in u and "_sop=7" in u
    assert "LH_Auction=1" in active_url("ps5", None, "auction")
    s = sold_url("ps5")
    assert "LH_Sold=1" in s and "LH_Complete=1" in s
    assert clean_item_url("https://www.ebay.co.uk/itm/sony-ps5/4567890123?_skw=ps5") == "https://www.ebay.co.uk/itm/4567890123"


def test_ebay_s_item_parser():
    rows = parse_search_html(EBAY_S_ITEM)
    assert len(rows) == 1  # placeholder + price range skipped
    r = rows[0]
    assert r["title"] == "Sony PS5 Disc Console 825GB"
    assert r["price"] == 329.99 and r["postage"] == 6.99
    assert r["condition"] == "Pre-owned"
    assert r["location"].startswith("Crawley")
    assert r["bids"] == 3 and r["auction"]
    assert r["url"] == "https://www.ebay.co.uk/itm/2345678901"
    assert r["image"].startswith("https://i.ebayimg.com")


def test_ebay_s_card_sold_parser():
    rows = parse_search_html(EBAY_S_CARD_SOLD, sold=True)
    assert len(rows) == 1
    r = rows[0]
    assert r["price"] == 310.0 and r["postage"] == 0.0
    assert r["sold_date"] == "12 Nov 2026"
    assert r["condition"] == "Pre-owned"
    assert r["image"] == "https://i.ebayimg.com/x.jpg"


def test_gumtree_parser():
    items = parse_results(GUMTREE)
    assert [i.price for i in items] == [400, 1250]
    assert items[0].url == "https://www.gumtree.com/p/ps5/sony-ps5-slim/1802302551"
    assert items[0].location == "Bromley, London" and items[0].is_collection
    assert items[1].image_url == "https://img.gumtree.com/b/86"
    assert items[1].distance_miles == 3
    assert "distance=25" in search_url("ps5", "RH19 1AA", 25)
    assert "search_location=uk" in search_url("ps5", "RH19 1AA", 0)


def test_facebook_parser_and_cookies():
    items = parse_marketplace_html(FB)
    assert [(i.title, i.price) for i in items] == [("PS5 Disc Edition", 250), ("Nintendo Switch Lite", 80)]
    assert items[0].url == "https://www.facebook.com/marketplace/item/111222333/"
    assert items[0].location == "Crawley, West Sussex"
    assert session_cookies("", "x") == []
    ck = session_cookies("123", "abc")
    assert {c["name"] for c in ck} == {"c_user", "xs"}


def test_cex_hit_mapping():
    b = hit_to_box(
        {
            "boxId": "SPS5825GBW003",
            "boxName": "Playstation 5 Console, 825GB, White, Discounted",
            "sellPrice": 470,
            "cashPriceCalculated": 300,
            "exchangePriceCalculated": 347,
            "categoryFriendlyName": "Playstation5 Consoles",
            "imageUrls": {"medium": "https://uk.static.webuy.com/product_images/Gaming/Playstation5 Consoles/x_m.jpg"},
        }
    )
    assert (b.cash, b.voucher, b.retail) == (300, 347, 470)
    assert b.url == "https://uk.webuy.com/product-detail?id=SPS5825GBW003"
    assert "%20" in b.image_url
    assert hit_to_box({"boxName": "x"}) is None
