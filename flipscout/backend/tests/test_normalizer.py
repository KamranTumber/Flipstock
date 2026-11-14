import pytest

from app.services.normalizer import (
    comp_query,
    condition_bucket,
    detect_category,
    is_accessory,
    match_score,
    normalize_title,
    red_flags,
)

T = 72  # default match threshold


def test_normalize_strips_fluff_and_aliases():
    n = normalize_title("RARE!! MINT Sony PlayStation 5 Console 825GB L@@K Bundle")
    assert "rare" not in n and "mint" not in n and "bundle" not in n
    assert "ps5" in n and "825gb" in n


@pytest.mark.parametrize(
    "title,flag",
    [
        ("PS5 Controller Box Only", "box only"),
        ("iPhone 13 Pro iCloud locked spares", "icloud locked"),
        ("RTX 3080 faulty no display", "faulty"),
        ("Xbox Series X spares or repairs", "spares/repairs"),
        ("MacBook Air M1 - READ DESCRIPTION", "read description"),
        ("iPad Air cracked screen", "damaged"),
        ("WANTED: PS5 console", "wanted ad"),
    ],
)
def test_red_flags(title, flag):
    assert flag in red_flags(title)


def test_clean_title_has_no_flags():
    assert red_flags("Sony PlayStation 5 Disc Edition, boxed, excellent") == []


def test_accessory_detection():
    assert is_accessory("PS5 DualSense Controller White")
    assert not is_accessory("PS5 Console with 2 controllers")
    assert not is_accessory("Sony PlayStation 5 Disc Console")
    assert is_accessory("iPhone 13 case leather")


def test_matching_same_product_scores_high():
    r = match_score("Sony PS5 Disc Edition Console 825GB", "Sony PlayStation 5 Console, Disc, 825GB, White, Boxed")
    assert r.score >= T, r


def test_controller_not_matched_to_console():
    r = match_score("PS5 Console Disc Edition", "Sony PS5 DualSense Wireless Controller")
    assert r.score < T
    assert "accessory vs device" in r.reasons


def test_box_only_not_matched_to_working_console():
    r = match_score("PS5 Console", "PS5 Console Box Only")
    assert r.score < T


def test_model_number_mismatch():
    assert match_score("RTX 3080 10GB", "NVIDIA GeForce RTX 3070 8GB").score < 50
    assert match_score("iPhone 13 128GB", "Apple iPhone 14 128GB").score < 50


def test_product_family_mismatch():
    assert match_score("PS5 console", "Xbox Series X 1TB Console").score < 50
    assert match_score("iPhone 13 128GB", "iPad 9th Gen 128GB").score < 50
    assert match_score("RTX 3080 10GB", "RX 6800 XT 16GB").score < 50


def test_variant_mismatch():
    assert match_score("iPhone 13 128GB Unlocked", "Apple iPhone 13 Pro Max 128GB Unlocked").score < T
    assert match_score("MacBook Air M1", "MacBook Pro M1").score < T


def test_storage_mismatch_penalised():
    same = match_score("iPhone 13 128GB", "Apple iPhone 13 128GB Midnight").score
    diff = match_score("iPhone 13 128GB", "Apple iPhone 13 512GB Midnight").score
    assert same >= T and diff < same


def test_gpu_match():
    assert match_score("MSI RTX 3080 Gaming X Trio 10GB", "NVIDIA GeForce RTX 3080 10GB MSI Gaming X Trio").score >= T


def test_special_edition_not_matched_to_standard_bundle():
    # Real false-positive seen against live CeX data.
    src = "Sony PlayStation 5 Console with Controller and Spider-Man 2 Game"
    assert match_score(src, "Playstation 5 Console, 825GB, Spider-Man w/Spider-Man Controller, Boxed").score < T
    assert match_score(src, "Playstation 5 Console, 825GB, White, Discounted").score >= T
    assert match_score("PS5 Spider-Man 2 Limited Edition console", "Playstation 5 Console, 825GB, Spider-Man w/Spider-Man Controller").score >= T


def test_negative_best_badge():
    from app.schemas import ExitChannel
    from app.services.profit import badges

    b, _ = badges(ExitChannel(channel="cex", label="x", available=True, profit=-6), None)
    assert b.startswith("No profitable exit")


def test_comp_query_stops_at_inclusions():
    q = comp_query("RARE PS5 Disc Console with 2 controllers and FIFA")
    assert q.startswith("ps5")
    assert "controllers" not in q and "fifa" not in q


def test_categories():
    assert detect_category("RTX 4070 Super") == "gpu"
    assert detect_category("PS5 Slim") == "console"
    assert detect_category("iPhone 15 Pro") == "apple"
    assert detect_category("AirPods Pro 2") == "audio"
    assert detect_category("Logitech G Pro mouse") == "peripheral"


def test_condition_bucket():
    assert condition_bucket("Brand New") == "new"
    assert condition_bucket("Pre-owned") == "used"
    assert condition_bucket("For parts or not working") == "parts"
    assert condition_bucket(None, "PS5 sealed") == "new"
