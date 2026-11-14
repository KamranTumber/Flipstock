from app.scrapers.demo import products_for
from app.services.geocode import clean_postcode, haversine_miles, pick_place

# Shape of a real postcodes.io /places?q=Guildford response (first hit is in Wales).
GUILDFORDS = [
    {"name_1": "Guildford", "local_type": "Suburban Area", "county_unitary": "Sir Benfro - Pembrokeshire", "region": "Wales", "latitude": 51.744, "longitude": -4.911},
    {"name_1": "Guildford", "local_type": "Town", "county_unitary": "Surrey", "region": "South East", "latitude": 51.239, "longitude": -0.576},
    {"name_1": "Guildford", "local_type": "Suburban Area", "county_unitary": "Cornwall", "region": "South West", "latitude": 50.190, "longitude": -5.399},
    {"name_1": "Guildford Park", "local_type": "Suburban Area", "county_unitary": "Surrey", "region": "South East", "latitude": 51.237, "longitude": -0.589},
]
RH19 = (51.1259, -0.0097)


def test_pick_place_prefers_town_and_proximity():
    lat, lng = pick_place(GUILDFORDS, "Guildford", near=RH19)
    assert round(haversine_miles(*RH19, lat, lng)) < 30


def test_pick_place_county_hint_wins():
    lat, _ = pick_place(GUILDFORDS, "Guildford", hint="Cornwall", near=RH19)
    assert lat == 50.190


def test_clean_postcode():
    assert clean_postcode("rh191aa") == "RH19 1AA"
    assert clean_postcode(" m1 1ae ") == "M1 1AE"
    assert clean_postcode("RH19") == "RH19"


def test_demo_products_relevant():
    names = [p.name for p in products_for("ps5 console")]
    assert names and all("PS5" in n or "PlayStation 5" in n for n in names)
    assert any("3080" in p.name for p in products_for("rtx 3080"))
