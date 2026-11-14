"""Title normalisation, red-flag detection and fuzzy comp matching.

The goal is to stop a "PS5 Controller Box Only" or "iPhone 13 iCloud locked" listing
being valued against a working console / phone, and to stop an iPhone 13 being
valued against iPhone 13 Pro Max sold prices.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

# Marketing fluff that adds nothing to identity of the product.
FLUFF_WORDS = {
    "rare", "mint", "look", "l@@k", "lqqk", "wow", "bundle", "bargain", "cheap", "fast",
    "free", "postage", "p&p", "pp", "delivery", "uk", "seller", "quick", "sale", "genuine",
    "official", "original", "authentic", "immaculate", "pristine", "perfect", "excellent",
    "condition", "great", "good", "fully", "working", "tested", "boxed", "unboxed", "brand",
    "new", "sealed", "used", "only", "ono", "offers", "offer", "collection", "collect",
    "nr", "no", "reserve", "must", "see", "hot", "deal", "amazing", "superb", "a+", "grade",
    "warranty", "receipt", "please", "discounted", "unlocked", "read", "the", "a", "an", "for", "in", "of", "&",
    "-", "/", "+", "|", "!", "!!", "!!!",
}

# Things that mean "this is not a working, complete product".
RED_FLAG_PATTERNS: dict[str, str] = {
    "spares/repairs": r"\bspares?\b|\brepairs?\b|\bfor parts\b|\bparts only\b",
    "faulty": r"\bfaulty\b|\bnot working\b|\bdoesn'?t work\b|\bno power\b|\bwon'?t turn on\b|\bboot ?loop\b|\bdead\b",
    "box only": r"\bbox only\b|\bempty box\b|\bbox and manual\b|\bcase only\b|\bpackaging only\b",
    "read description": r"\bread (the )?desc(ription)?\b|\bsee desc(ription)?\b|\bplease read\b",
    "icloud locked": r"\bicloud\b|\bactivation lock(ed)?\b|\bfmi on\b|\bfind my (iphone )?on\b|\bgoogle lock(ed)?\b|\bfrp\b",
    "network blacklisted": r"\bblacklist(ed)?\b|\bbad esn\b|\bbarred\b|\bblocked imei\b",
    "damaged": r"\bbroken\b|\bcracked\b|\bdamaged\b|\bsmashed\b|\bwater damage\b|\bbent\b",
    "untested": r"\buntested\b|\bas is\b|\bsold as seen\b",
    "replica": r"\breplica\b|\bdupe\b|\bfake\b|\bdummy\b|\bclone\b",
    "photo/listing only": r"\bphoto of\b|\bpicture of\b|\bimage only\b",
    "wanted ad": r"\bwanted\b|\blooking for\b|\bwtb\b|\bswap(s)? (for|only)\b",
}
_RED_FLAG_RE = {k: re.compile(v, re.I) for k, v in RED_FLAG_PATTERNS.items()}

# Words that make a title an accessory rather than the device itself.
ACCESSORY_WORDS = {
    "controller", "controllers", "pad", "joycon", "joy-con", "case", "cover", "charger",
    "cable", "lead", "box", "stand", "skin", "sticker", "dock", "strap", "adapter",
    "remote", "mount", "protector", "manual", "faceplate", "shell", "backplate",
    "bracket", "shroud", "fan", "cooler", "heatsink", "riser", "plate", "sleeve", "pouch",
    "tips", "battery", "replacement", "housing", "hdmi",
}
INCLUSION_WORDS = {"with", "w", "inc", "incl", "includes", "including", "and", "plus", "+", "&", "x2", "2x"}
# Explicit "this is the main unit" words: "PS5 console box" is still a console.
DEVICE_WORDS = {"console", "laptop", "computer", "pc", "handheld", "system"}

# Variant tokens that change value a lot.
VARIANT_WORDS = {
    "pro", "max", "mini", "ultra", "plus", "ti", "super", "xt", "xtx", "lite", "oled",
    "digital", "slim", "se", "air", "fe",
}

ALIASES: list[tuple[str, str]] = [
    (r"\bplay\s*station\s*5\b", "ps5"),
    (r"\bplay\s*station\s*4\b", "ps4"),
    (r"\bplaystation\s*portal\b", "ps portal"),
    (r"\bps\s*5\b", "ps5"),
    (r"\bps\s*4\b", "ps4"),
    (r"\bnintendo\s+switch\b", "switch"),
    (r"\bxbox\s+series\s+x\b", "xbox seriesx"),
    (r"\bxbox\s+series\s+s\b", "xbox seriess"),
    (r"\bgeforce\b", ""),
    (r"\bnvidia\b", ""),
    (r"\bradeon\b", ""),
    (r"\b(rtx|gtx|rx)\s*(\d{3,4})\b", r"\1\2"),
    (r"\b(\d+)\s*(gb|tb)\b", r"\1\2"),
    (r"\bi\s*phone\b", "iphone"),
    (r"\bair\s*pods\b", "airpods"),
    (r"\bmac\s*book\b", "macbook"),
    (r"\b2nd\s+gen(eration)?\b", "gen2"),
    (r"\b3rd\s+gen(eration)?\b", "gen3"),
    (r"\b(\d)(st|nd|rd|th)\s+gen(eration)?\b", r"gen\1"),
    (r"\bgen(eration)?\s*(\d)\b", r"gen\2"),
]
_ALIASES = [(re.compile(p, re.I), r) for p, r in ALIASES]

STORAGE_RE = re.compile(r"^\d+(gb|tb)$")
COLOUR_WORDS = {
    "black", "white", "silver", "grey", "gray", "gold", "blue", "red", "green", "purple",
    "pink", "midnight", "starlight", "graphite", "titanium", "natural", "space", "yellow",
}


# Special / limited edition identity. Matters when it is *part of the product name*
# ("PS5 Spider-Man Limited Edition") rather than an included extra ("PS5 with Spider-Man 2").
LIMITED_RE = re.compile(r"limited|special edition|collector|anniversary|\b\d+th\b", re.I)
FRANCHISE_RE = re.compile(
    r"spider-?man|god of war|call of duty|\bcod\b|fortnite|pok[eé]mon|zelda|mario|animal crossing|\bhalo\b|"
    r"cyberpunk|hogwarts|final fantasy|astro ?bot|death stranding|starfield|diablo|\bfifa\b|\bfc\s?2\d\b",
    re.I,
)


def edition_identity(title: str) -> tuple[bool, frozenset[str]]:
    """(is a special edition?, franchise names) for the identity part of a title."""
    core = core_text(title).lower()
    fr = frozenset(re.sub(r"[\s-]", "", f) for f in FRANCHISE_RE.findall(core))
    return bool(fr or LIMITED_RE.search(core)), fr


def core_text(title: str) -> str:
    """Product identity part of a title: everything before the first inclusion word."""
    out = []
    for t in _basic_clean(title).split():
        if t in INCLUSION_WORDS and out:
            break
        out.append(t)
    return " ".join(out)


@dataclass
class MatchResult:
    score: float
    reasons: list[str] = field(default_factory=list)


def red_flags(title: str) -> list[str]:
    return [name for name, rx in _RED_FLAG_RE.items() if rx.search(title or "")]


def _basic_clean(title: str) -> str:
    t = (title or "").lower()
    t = re.sub(r"[☀-➿\U0001F300-\U0001FAFF]", " ", t)  # emoji
    t = t.replace("l@@k", " ").replace("lqqk", " ")
    for rx, rep in _ALIASES:
        t = rx.sub(rep, t)
    t = re.sub(r"[^a-z0-9+&.\- ]", " ", t)
    t = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", t)  # keep decimals like 2.5
    return re.sub(r"\s+", " ", t).strip()


def normalize_title(title: str) -> str:
    """Lower-case, alias, strip fluff + red-flag words. Used for matching and comp queries."""
    tokens = [tok for tok in _basic_clean(title).split() if tok not in FLUFF_WORDS]
    return " ".join(tokens)


def comp_query(title: str, max_tokens: int = 7) -> str:
    """Short search string for comp lookups: identity tokens only, no colours."""
    tokens = [t for t in normalize_title(title).split() if t not in COLOUR_WORDS and t not in INCLUSION_WORDS]
    # Stop at inclusion words in the original ordering ("ps5 with 2 controllers" -> "ps5").
    out: list[str] = []
    for t in _basic_clean(title).split():
        if t in INCLUSION_WORDS and out:
            break
        if t in tokens and t not in out:
            out.append(t)
    return " ".join(out[:max_tokens]) or " ".join(tokens[:max_tokens])


def _tokens(norm: str) -> list[str]:
    return norm.split()


def storage_tokens(norm: str) -> set[str]:
    return {t for t in _tokens(norm) if STORAGE_RE.match(t)}


def model_numbers(norm: str) -> set[str]:
    nums: set[str] = set()
    for t in _tokens(norm):
        if STORAGE_RE.match(t) or re.match(r"^\d+(mm|hz|w|v|mah|in|inch|\")$", t):
            continue
        for run in re.findall(r"\d+", t):
            nums.add(run.lstrip("0") or "0")
    return nums


FAMILY_TOKENS = {
    "ps5", "ps4", "ps3", "xbox", "switch", "iphone", "ipad", "macbook", "imac", "airpods", "deck",
    "galaxy", "pixel", "quest", "watch", "kindle", "gopro", "dji",
}


def product_families(norm: str) -> set[str]:
    fams = {t for t in _tokens(norm) if t in FAMILY_TOKENS}
    for t in _tokens(norm):
        if re.match(r"^(rtx|gtx)\d", t):
            fams.add("nvidia")
        elif re.match(r"^rx\d", t):
            fams.add("amd")
    return fams


def variant_tokens(norm: str) -> set[str]:
    return {t for t in _tokens(norm) if t in VARIANT_WORDS}


def is_accessory(title: str) -> bool:
    toks = _basic_clean(title).split()
    first_acc = next((i for i, t in enumerate(toks) if t in ACCESSORY_WORDS), None)
    if first_acc is None:
        return False
    if any(t in DEVICE_WORDS for t in toks[:first_acc]):
        return False  # "PS5 console box" / "PS5 console with controller" is a console
    for i, t in enumerate(toks):
        if t in ACCESSORY_WORDS:
            window = toks[max(0, i - 3) : i]
            quantity = i > 0 and re.fullmatch(r"[1-4]x?|x[1-4]", toks[i - 1])  # "2 controllers"
            if not quantity and not any(w in INCLUSION_WORDS for w in window):
                return True
    return False


def match_score(source_title: str, comp_title: str) -> MatchResult:
    """0-100 similarity that punishes model / variant / storage / accessory mismatches."""
    a, b = normalize_title(source_title), normalize_title(comp_title)
    if not a or not b:
        return MatchResult(0, ["empty title"])

    def blend(x: str, y: str) -> float:
        return 0.6 * fuzz.token_set_ratio(x, y) + 0.4 * fuzz.token_sort_ratio(x, y) if x and y else 0.0

    # Also compare the identity part only, so bundled extras ("with 2 controllers and FIFA")
    # don't drag down an otherwise exact product match.
    ca, cb = normalize_title(core_text(source_title)), normalize_title(core_text(comp_title))
    score = max(blend(a, b), blend(ca, cb))
    reasons: list[str] = []

    fam_a, fam_b = product_families(a), product_families(b)
    if fam_a and fam_b and fam_a.isdisjoint(fam_b):
        score = min(score, 30)
        reasons.append(f"different product family {sorted(fam_a)} vs {sorted(fam_b)}")

    na, nb = model_numbers(a), model_numbers(b)
    if na and nb and not (na & nb):
        score = min(score, 35)
        reasons.append(f"model mismatch {sorted(na)} vs {sorted(nb)}")
    elif nb - na and na:
        score -= 8 * len(nb - na)
        reasons.append(f"comp has extra model numbers {sorted(nb - na)}")
    elif nb and not na:
        score -= 10
        reasons.append("source has no model number")

    va, vb = variant_tokens(a), variant_tokens(b)
    diff = va ^ vb
    if diff:
        score -= 14 * len(diff)
        reasons.append(f"variant mismatch {sorted(diff)}")

    sa, sb = storage_tokens(a), storage_tokens(b)
    if sa and sb and not (sa & sb):
        score -= 18
        reasons.append(f"storage mismatch {sorted(sa)} vs {sorted(sb)}")

    (sa_, fa_), (sb_, fb_) = edition_identity(source_title), edition_identity(comp_title)
    if sa_ != sb_ or fa_ != fb_:
        score = min(score, 55)
        reasons.append(f"special edition mismatch {sorted(fa_ ^ fb_) or 'limited vs standard'}")

    if is_accessory(source_title) != is_accessory(comp_title):
        score = min(score, 30)
        reasons.append("accessory vs device")

    fa, fb = bool(red_flags(source_title)), bool(red_flags(comp_title))
    if fa != fb:
        score = min(score, 25)
        reasons.append("condition (spares/faulty) mismatch")

    return MatchResult(round(max(0.0, min(100.0, score)), 1), reasons)


# ---------------------------------------------------------------- categories

CATEGORY_RULES: list[tuple[str, re.Pattern]] = [
    ("gpu", re.compile(r"\b(rtx|gtx|rx)\s?\d{3,4}|graphics card|\bgpu\b|\barc a\d{3}", re.I)),
    ("console", re.compile(r"\bps[45]\b|playstation|xbox|switch|steam deck|rog ally|legion go|\bconsole\b", re.I)),
    ("apple", re.compile(r"iphone|ipad|macbook|imac|mac mini|apple watch|airpods|apple", re.I)),
    ("audio", re.compile(r"headphones?|earbuds?|speaker|soundbar|sony wh|bose|sennheiser|beats|airpods", re.I)),
    ("peripheral", re.compile(r"keyboard|mouse|controller|webcam|monitor|ssd|nvme|\bram\b|ddr[45]", re.I)),
]

SMALL_CATEGORIES = {"audio", "peripheral"}


def detect_category(title: str) -> str:
    for name, rx in CATEGORY_RULES:
        if rx.search(title or ""):
            if name == "apple" and re.search(r"airpods|apple watch", title, re.I):
                return "audio"
            return name
    return "other"


def condition_bucket(condition: str | None, title: str = "") -> str:
    text = f"{condition or ''} {title}".lower()
    if red_flags(text) or "for parts" in text:
        return "parts"
    if re.search(r"\bbrand new\b|\bnew\b|\bsealed\b|\bunopened\b", (condition or "").lower()):
        return "new"
    if re.search(r"\bsealed\b|\bbnib\b|\bbrand new\b", (title or "").lower()):
        return "new"
    return "used"
