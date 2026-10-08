import json, os, re
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

BASE = Path.home() / "new_scraper"
OUT = BASE / "ads" / "daily_ads_20_categories.json"

CATEGORIES = [
    "smartwatches",
    "headphones-earbuds",
    "speakers",
    "ceiling-fans",
    "water-purifiers",
    "mixer-grinders",
    "drones",
    "desktop-computers",
    "geysers",
    "laptops",
    "smart-phones",
    "refrigerators",
    "smart-tvs",
    "air-coolers",
    "vacuum-cleaners",
    "air-conditioners",
    "induction-cooktops",
    "washing-machines",
    "tablets",
    "microwave-ovens",
]

CATEGORY_DISPLAY = {
    "smartwatches": "Smartwatches",
    "headphones-earbuds": "Headphones & Earbuds",
    "speakers": "Speakers",
    "ceiling-fans": "Ceiling Fans",
    "water-purifiers": "Water Purifiers",
    "mixer-grinders": "Mixer Grinders",
    "drones": "Drones",
    "desktop-computers": "Desktop Computers",
    "geysers": "Geysers",
    "laptops": "Laptops",
    "smart-phones": "Smartphones",
    "refrigerators": "Refrigerators",
    "smart-tvs": "Smart TVs",
    "air-coolers": "Air Coolers",
    "vacuum-cleaners": "Vacuum Cleaners",
    "air-conditioners": "Air Conditioners",
    "induction-cooktops": "Induction Cooktops",
    "washing-machines": "Washing Machines",
    "tablets": "Tablets",
    "microwave-ovens": "Microwave Ovens",
}

# Category relevance is used only for ad selection. The MongoDB category
# itself is never modified.
CATEGORY_RELEVANCE = {
    "smartwatches": {
        "must_any": ["smartwatch", "smart watch", "watch"],
        "exclude_any": ["watch strap", "watch band", "watch case", "screen protector"],
    },
    "headphones-earbuds": {
        "must_any": ["headphone", "earbud", "earbuds", "headset", "neckband"],
        "exclude_any": ["replacement", "ear pad", "earpad", "case only"],
    },
    "speakers": {
        "must_any": ["speaker", "soundbar", "home theatre", "home theater"],
        "exclude_any": ["speaker stand", "replacement", "remote only"],
    },
    "ceiling-fans": {
        "must_any": ["ceiling fan", "ceilingfans", "ceiling fan"],
        "exclude_any": ["chain extender", "extension chain", "fan cord", "replacement"],
    },
    "water-purifiers": {
        "must_any": ["water purifier", "water purification", "ro water purifier"],
        "exclude_any": ["survival gear", "camping", "portable filter", "hiking"],
    },
    "mixer-grinders": {
        "must_any": ["mixer grinder", "mixer-grinder", "mixer", "grinder", "juicer mixer", "blender"],
        "exclude_any": ["replacement jar", "jar only", "spare jar", "replacement", "parts only"],
    },
    "drones": {
        "must_any": ["drone", "quadcopter"],
        "exclude_any": ["drone part", "drone propeller", "propeller only"],
    },
    "desktop-computers": {
        "must_any": ["desktop", "desktop computer", "pc", "tower pc", "all in one", "aio", "mini pc", "nuc"],
        "exclude_any": ["monitor only", "keyboard only", "mouse only"],
    },
    "geysers": {
        "must_any": ["geyser", "water heater", "water heater for home"],
        "exclude_any": ["heater rod only", "heating element only", "immersion rod only"],
    },
    "laptops": {
        "must_any": ["laptop", "notebook", "chromebook"],
        "exclude_any": ["laptop bag", "laptop stand", "laptop sleeve", "replacement"],
    },
    "smart-phones": {
        "must_any": ["smartphone", "smart phone", "mobile phone", "mobile", "android phone"],
        "exclude_any": ["phone case", "screen protector", "replacement", "dummy phone", "feature phone"],
    },
    "refrigerators": {
        "must_any": ["refrigerator", "fridge"],
        "exclude_any": ["refrigerator stand", "cover only", "replacement"],
    },
    "smart-tvs": {
        "must_any": ["smart tv", "smart led tv", "smart qled", "smart oled", "television", " tv "],
        "exclude_any": ["tv wall mount", "remote only", "tv cover", "monitor"],
    },
    "air-coolers": {
        "must_any": ["air cooler", "air coolers", "desert air cooler", "tower air cooler", "personal air cooler"],
        "exclude_any": ["cooler pump", "cooler motor", "replacement", "water cooler"],
    },
    "vacuum-cleaners": {
        "must_any": ["vacuum cleaner", "vacuum", "robot vacuum"],
        "exclude_any": ["vacuum bag", "vacuum filter only", "replacement", "vacuum part"],
    },
    "air-conditioners": {
        "must_any": ["air conditioner", "air conditioning", "split ac", "window ac", "inverter ac", " ac "],
        "exclude_any": ["deep freezer", "freezer", "air cooler", "ac cover"],
    },
    "induction-cooktops": {
        "must_any": ["induction cooktop", "induction cooktop stove", "induction stove", "induction"],
        "exclude_any": ["hookah", "coil hot plate", "hot plate", "radiant cooktop", "gas stove", "cookware", "pan only"],
    },
    "washing-machines": {
        "must_any": ["washing machine", "washer", "washing-machine"],
        "exclude_any": ["dishwasher", "washer cover", "washing machine cleaner", "replacement"],
    },
    "tablets": {
        "must_any": ["tablet", "android tablet", "ipad"],
        "exclude_any": ["tablet case", "tablet cover", "tablet stand", "replacement"],
    },
    "microwave-ovens": {
        "must_any": ["microwave", "microwave oven"],
        "exclude_any": ["otg", "oven toaster grill", "toaster oven", "electric oven"],
    },
}

BUDGET_TARGETS = {
    "smartwatches": [2000, 3000, 5000, 7500, 10000, 15000, 20000, 30000],
    "headphones-earbuds": [1000, 2000, 3000, 5000, 7500, 10000, 15000, 20000],
    "speakers": [2000, 3000, 5000, 7500, 10000, 15000, 25000, 50000],
    "ceiling-fans": [2000, 3000, 4000, 5000, 7500, 10000, 15000],
    "water-purifiers": [5000, 7500, 10000, 15000, 20000, 30000, 50000],
    "mixer-grinders": [2000, 3000, 5000, 7500, 10000, 15000],
    "drones": [5000, 10000, 15000, 20000, 30000, 50000, 75000, 100000],
    "desktop-computers": [20000, 30000, 40000, 50000, 75000, 100000, 150000],
    "geysers": [5000, 7500, 10000, 15000, 20000, 30000],
    "laptops": [30000, 40000, 50000, 60000, 75000, 100000, 150000],
    "smart-phones": [10000, 15000, 20000, 25000, 30000, 40000, 50000, 75000, 100000],
    "refrigerators": [20000, 25000, 30000, 40000, 50000, 75000, 100000],
    "smart-tvs": [15000, 20000, 25000, 30000, 40000, 50000, 75000, 100000],
    "air-coolers": [5000, 7500, 10000, 15000, 20000, 30000],
    "vacuum-cleaners": [5000, 7500, 10000, 15000, 20000, 30000],
    "air-conditioners": [25000, 30000, 40000, 50000, 60000, 75000],
    "induction-cooktops": [1500, 2000, 3000, 5000, 7500],
    "washing-machines": [15000, 20000, 25000, 30000, 40000, 50000, 75000],
    "tablets": [10000, 15000, 20000, 25000, 30000, 40000, 50000, 75000],
    "microwave-ovens": [5000, 7500, 10000, 15000, 20000, 30000],
}

# For these categories, RAM/storage are true variant identifiers.
# Other categories rely primarily on exact brand + model identity.
MEMORY_VARIANT_CATEGORIES = {
    "smart-phones",
    "laptops",
    "tablets",
    "desktop-computers",
}

PLATFORMS = ("amazon", "flipkart", "croma")

MAX_BUDGET_ADS = 3
MAX_BRAND_ADS = 3
MAX_COMPARISON_ADS = 3
PRODUCTS_PER_AD = 5

MIN_PLATFORMS_FOR_RECOMMENDATION = 2
MIN_COMPARISON_SAVING_PCT = 2.0
MAX_COMPARISON_SPREAD_PCT = 35.0

# Scan the full category dataset. The earlier 5,000-document cap
# could silently hide valid products and cross-platform matches.
MONGO_LIMIT = None

GENERIC_BRANDS = {
    "add", "ai", "android", "bluetooth", "computer", "desktop",
    "earbuds", "good", "in ear", "kids", "mobile", "phone",
    "portable", "smart", "tablet", "truly", "wireless",
    "10", "10 1", "2025", "7"
}

SELLER_WORDS = {
    "store", "shop", "online", "seller", "trader", "traders",
    "retail", "retailer", "hub", "mart", "enterprise", "enterprises",
    "world", "deals",
}


GENERIC_MODEL_WORDS = {
    "smartphone", "smart", "phone", "mobile", "android",
    "with", "the", "new", "latest", "official", "5g", "4g",
    "gb", "tb", "ram", "storage", "mah"
}

MODEL_SUFFIX_WORDS = {
    "fe", "pro", "plus", "max", "mini", "lite", "ultra",
    "neo", "power", "edge", "prime", "play", "note", "se"
}

COMPARISON_MODEL_STOP_WORDS = {
    "smartphone", "smart", "phone", "mobile", "android", "with", "the",
    "new", "latest", "official", "online", "buy", "sale", "original",
    "gb", "tb", "ram", "rom", "storage", "memory", "mah", "battery",
    "inch", "inches", "cm", "mm", "kg", "g", "l", "ml", "litre",
    "litres", "ton", "tons", "w", "watts", "hz", "nm", "mp",
    "star", "stars", "year", "model", "series", "display", "screen",
    "wifi", "wi", "bluetooth", "lte", "cellular", "5g", "4g",
    "4k", "8k", "qled", "oled", "led", "hd", "fhd",
}

COMPARISON_IGNORE_CONTEXT = {
    "by", "urban", "company", "uc", "only", "for", "home",
    "device", "product", "smartchoice", "professional",
    "launched", "newly", "featured", "online",
    "plus", "uv", "ro", "uf", "utc", "copper", "alkaline",
    "water", "purifier", "l", "litre", "litres",
}

COMPARISON_TECH_WORDS = {
    "mediatek", "dimensity", "snapdragon", "ryzen", "intel",
    "amd", "core", "processor", "mali", "radeon", "graphics",
    "qualcomm", "apple", "nvidia",
}

COMPARISON_VARIANT_WORDS = {
    "submarine", "absolute", "flip", "window", "split",
    "semi-automatic", "semi", "fully-automatic", "fully",
    "washer-dryer", "dryer",
}

COMPARISON_FAMILY_NUMBER_WORDS = {
    "note", "iphone", "watch", "tab", "series",
}

COMPARISON_YEAR_WORDS = {
    str(year) for year in range(2020, 2036)
}


load_dotenv(BASE / ".env")

MONGO_URI = (
    os.getenv("MONGODB_URI")
    or os.getenv("MONGO_URI")
    or os.getenv("MONGODB_URL")
)

DB_NAME = os.getenv("MONGODB_DB", "trustfolio")
COLLECTION = os.getenv("PRODUCT_COLLECTION", "my_products")

if not MONGO_URI:
    raise RuntimeError("MongoDB URI not found in ~/new_scraper/.env")

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
products = client[DB_NAME][COLLECTION]


def clean(value):
    return re.sub(
        r"\s+",
        " ",
        re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
    ).strip()


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        m = re.search(r"\d+(?:\.\d+)?", str(value or "").replace(",", ""))
        return float(m.group()) if m else 0.0


def price(p):
    p_inr = p.get("price_inr")
    if p_inr is not None:
        value = number(p_inr)
        if value:
            return value
    return number(p.get("price"))


def rating_num(p):
    raw = p.get("average_rating")
    if raw in (None, ""):
        raw = p.get("rating")
    return number(raw)


def platform(p):
    return str(p.get("platform") or "").strip().lower()


def brand(p):
    return str(p.get("brand") or "").strip()


def title(p):
    return str(p.get("title") or "").strip()


def normalize_brand(p):
    return clean(brand(p))


def extract_capacities(value):
    text = clean(value)
    return [
        amount + unit
        for amount, unit in re.findall(
            r"\b(\d{1,4})\s*(gb|tb)\b",
            text
        )
    ]


def spec_value(p, names):
    """
    Normalize RAM/storage from structured specs or product title.

    Handles:
      4GB RAM, 128GB Storage
      6+128GB
      6GB+128GB
      6/128GB
      8GB RAM + 128GB
    """
    specs = p.get("specifications") or {}
    normalized = {
        clean(k): clean(v)
        for k, v in specs.items()
        if v not in (None, "")
    }

    wanted_clean = [clean(x) for x in names]
    is_ram = "ram" in wanted_clean

    for wanted in wanted_clean:
        for key, value in normalized.items():
            if key == wanted or wanted in key:
                caps = extract_capacities(value)
                if caps:
                    return caps[0] if is_ram else caps[-1]
                return ""

    t = title(p).lower()

    combined = re.search(
        r"\b(\d{1,3})\s*(gb|tb)?\s*(?:\+|/)\s*"
        r"(\d{1,4})\s*(gb|tb)\b",
        t
    )

    if is_ram:
        if combined:
            return combined.group(1) + (
                combined.group(2) or combined.group(4)
            )

        m = re.search(
            r"\b(\d{1,3})\s*(gb|tb)\s*ram\b",
            t
        )
        if m:
            return m.group(1) + m.group(2)

        m = re.search(
            r"\bram\s*(\d{1,3})\s*(gb|tb)\b",
            t
        )
        if m:
            return m.group(1) + m.group(2)

        return ""

    m = re.search(
        r"\b(\d{1,4})\s*(gb|tb)\s*(?:storage|rom)\b",
        t
    )
    if m:
        return m.group(1) + m.group(2)

    if combined:
        return combined.group(3) + combined.group(4)

    capacities = extract_capacities(t)
    ram_match = re.search(
        r"\b(\d{1,3})\s*(gb|tb)\s*ram\b",
        t
    )

    for capacity in capacities:
        if ram_match:
            ram_capacity = ram_match.group(1) + ram_match.group(2)
            if capacity == ram_capacity:
                continue
        return capacity

    return ""


def model_signature(p):
    """
    Extract a conservative product model identity.
    The same function is used across all 20 categories; model numbers
    and model suffixes are preferred over marketing/specification words.

    Examples:
      Samsung Galaxy A37 5G       -> galaxy a37
      Apple iPhone 18 Pro         -> iphone 18 pro
      Redmi Note 14 Pro+ 5G       -> note 14 pro plus
      OnePlus 13R                 -> 13r
    """
    raw = title(p).lower()
    raw = raw.split("|")[0]
    raw = raw.replace("+", " plus ")
    raw = re.sub(r"[^a-z0-9]+", " ", raw)
    tokens = raw.split()

    brand_tokens = set(clean(brand(p)).split())

    candidates = []

    for i, token in enumerate(tokens):
        if token in GENERIC_MODEL_WORDS or token in brand_tokens:
            continue

        is_alnum_model = re.fullmatch(
            r"(?=.*[a-z])(?=.*\d)[a-z0-9]{2,10}",
            token
        )

        is_numeric_model = re.fullmatch(r"\d{2,4}", token)

        if not (is_alnum_model or is_numeric_model):
            continue

        part = []

        # Keep one useful family word immediately before the model.
        if i > 0:
            prev = tokens[i - 1]
            if prev in {"galaxy", "iphone", "note", "nord", "pixel"}:
                part.append(prev)

        part.append(token)

        # Keep consecutive model suffixes such as:
        # pro, plus -> "pro plus"
        j = i + 1
        while j < len(tokens) and tokens[j] in MODEL_SUFFIX_WORDS:
            part.append(tokens[j])
            j += 1

        candidates.append(part)

    if candidates:
        # Prefer the longest useful model phrase.
        best = max(
            candidates,
            key=lambda x: (
                len(x),
                sum(
                    1 for t in x
                    if re.search(r"\d", t)
                )
            )
        )
        return " ".join(dict.fromkeys(best))

    # Conservative fallback for unusual titles.
    fallback = [
        t for t in tokens
        if t not in GENERIC_MODEL_WORDS
        and t not in brand_tokens
    ]
    return " ".join(fallback[:3])


def comparison_model_signature(p):
    """
    Strict model identity used ONLY for price-comparison ads.

    It deliberately rejects plain capacity/size/year numbers such as:
      1200mm, 750W, 308L, 2026, 15-inch.

    It accepts strong model tokens such as:
      fx3, m3, s20r, p4r, v12, a11, s10.

    It also captures product-family context so:
      Fastrack Marvellous FX3 != Fastrack Magnus FX3
      Rockerz Plus 550 != Rockerz 550
    """
    raw = title(p).lower().split("|")[0]
    raw = raw.replace("+", " plus ")
    raw = re.sub(r"[^a-z0-9]+", " ", raw)
    tokens = raw.split()

    brand_tokens = set(clean(brand(p)).split())
    candidates = []

    def useful_context(token):
        if (
            token in brand_tokens
            or token in COMPARISON_MODEL_STOP_WORDS
            or token in COMPARISON_IGNORE_CONTEXT
            or token in COMPARISON_TECH_WORDS
            or token in COMPARISON_YEAR_WORDS
        ):
            return False

        if re.fullmatch(
            r"\d+(?:\.\d+)?(?:gb|tb|mah|hz|mm|cm|kg|g|l|ml|w|watts|inch|inches|ton|tons|nm|mp|star|stars|k)",
            token,
        ):
            return False

        return True

    def prefix_context(index, max_words=2):
        out = []
        j = index - 1

        while j >= 0 and len(out) < max_words:
            tok = tokens[j]

            if useful_context(tok):
                out.append(tok)

            # Stop before drifting too far into marketing copy.
            if j < index - 1 and tok in COMPARISON_MODEL_STOP_WORDS:
                break

            j -= 1

        return list(reversed(out))

    for i, token in enumerate(tokens):
        if token in brand_tokens:
            continue

        if token in COMPARISON_MODEL_STOP_WORDS:
            continue

        if token in COMPARISON_YEAR_WORDS:
            continue

        # Ignore explicit specification/capacity tokens.
        if re.fullmatch(
            r"\d+(?:\.\d+)?(?:gb|tb|mah|hz|mm|cm|kg|g|l|ml|w|watts|inch|inches|ton|tons|nm|mp|star|stars|k)",
            token,
        ):
            continue

        # Strong mixed letter+digit model token.
        if re.fullmatch(
            r"(?=.*[a-z])(?=.*\d)[a-z0-9]{2,15}",
            token,
        ):
            part = prefix_context(i)
            part.append(token)

            j = i + 1
            while (
                j < len(tokens)
                and tokens[j] in MODEL_SUFFIX_WORDS
            ):
                part.append(tokens[j])
                j += 1

            candidates.append((3, len(part), part))
            continue

        # Family word + numeric model:
        # Note 14 Pro, iPhone 18 Pro, Watch SE 3.
        if (
            token in COMPARISON_FAMILY_NUMBER_WORDS
            and i + 1 < len(tokens)
            and re.fullmatch(r"\d{1,4}", tokens[i + 1])
        ):
            part = prefix_context(i)
            part.extend([token, tokens[i + 1]])

            j = i + 2
            while (
                j < len(tokens)
                and tokens[j] in MODEL_SUFFIX_WORDS
            ):
                part.append(tokens[j])
                j += 1

            candidates.append((3, len(part), part))
            continue

        # SE 3 / FE 2 style model naming.
        if (
            token in MODEL_SUFFIX_WORDS
            and i + 1 < len(tokens)
            and re.fullmatch(r"\d{1,2}", tokens[i + 1])
        ):
            part = prefix_context(i)
            part.extend([token, tokens[i + 1]])
            candidates.append((3, len(part), part))
            continue

        # Numeric model only when there is meaningful product-family
        # context and the number is not a unit/capacity.
        if re.fullmatch(r"\d{2,4}", token):
            prev = prefix_context(i)

            if not prev:
                continue

            part = prev + [token]

            j = i + 1
            while (
                j < len(tokens)
                and tokens[j] in MODEL_SUFFIX_WORDS
            ):
                part.append(tokens[j])
                j += 1

            candidates.append((1, len(part), part))

    if not candidates:
        return ""

    # Prefer strong alphanumeric/family-number models over generic
    # numeric models.
    _, _, best = max(
        candidates,
        key=lambda x: (x[0], x[1], sum(re.search(r"\d", t) is not None for t in x[2]))
    )

    return " ".join(dict.fromkeys(best))


def laptop_cpu_signature(p):
    """
    Extract the processor SKU/family where the title exposes one.

    Examples:
      Intel Core 5 120U   -> 120u
      Intel Core Ultra 5 226V -> 226v
      Intel Core i5 13450HX -> 13450hx
      Ryzen 7 6800H       -> 6800h

    A missing CPU signature is UNKNOWN.
    """
    text = clean(title(p))

    patterns = [
        r"\bintel\s+(?:core\s+)?(?:ultra\s+)?(?:i[3579]|[3579])\s*"
        r"(\d{3,5}[a-z]{0,3})\b",
        r"\bryzen\s+[3579]\s+(\d{3,5}[a-z]{0,3})\b",
    ]

    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1).lower()

    return ""


def comparison_variant_attributes(p, category):
    """
    Extract non-RAM/storage variant markers that can make two listings
    different versions of the same model.
    """
    text = title(p).lower()
    attrs = {}

    if category == "smartwatches":
        m = re.search(r"\b(3[5-9]|4\d|5\d)\s*mm\b", text)
        if m:
            attrs["size_mm"] = m.group(1) + "mm"

        if re.search(r"\bbluetooth\b", text):
            attrs["connectivity"] = "bluetooth"
        elif re.search(r"\b(?:lte|cellular)\b", text):
            attrs["connectivity"] = "cellular"
        elif re.search(r"\b5g\b", text):
            attrs["connectivity"] = "5g"
        elif re.search(r"wi[\s-]?fi\b", text):
            attrs["connectivity"] = "wifi"

    elif category == "tablets":
        if re.search(r"wi[\s-]?fi\s*(?:\+\s*)?5g", text):
            attrs["connectivity"] = "5g"
        elif re.search(r"\b(?:lte|cellular)\b", text):
            attrs["connectivity"] = "cellular"
        elif re.search(r"\b5g\b", text):
            attrs["connectivity"] = "5g"
        elif re.search(r"wi[\s-]?fi\s+only", text):
            attrs["connectivity"] = "wifi"
        elif re.search(r"wi[\s-]?fi\b", text):
            attrs["connectivity"] = "wifi"

    if category == "laptops":
        cpu = laptop_cpu_signature(p)
        if cpu:
            attrs["cpu"] = cpu

    # Strong product-family variants.
    for marker in (
        "submarine",
        "absolute",
        "window",
        "washer dryer",
        "washer-dryer",
        "2 in 1",
        "2-in-1",
    ):
        if marker in text:
            attrs["product_variant"] = marker
            break

    return attrs


def comparison_variants_compatible(products_for_model, category):
    """
    Require agreement for explicit variant attributes.

    For these attributes, missing data is NOT silently accepted once any
    platform exposes the attribute:
      - smartwatch size/connectivity
      - tablet connectivity
      - laptop CPU
      - strong product-family variants

    This is intentionally conservative for price-comparison ads.
    """
    attrs = [
        comparison_variant_attributes(p, category)
        for p in products_for_model
    ]

    keys = set()
    for item in attrs:
        keys.update(item.keys())

    strict_all_keys = {
        "size_mm",
        "connectivity",
        "cpu",
        "product_variant",
    }

    for key in keys:
        known = [
            item.get(key)
            for item in attrs
            if item.get(key)
        ]

        if len(set(known)) > 1:
            return False

        if key in strict_all_keys and len(known) != len(attrs):
            return False

    return True


def category_relevance_score(p, category):
    """
    Score title relevance for ad selection.

    Returns:
      -1 for an explicitly excluded product
       0 for no clear category signal
      1+ for a relevant product
    """
    rule = CATEGORY_RELEVANCE.get(category)
    if not rule:
        return 1

    text = " " + clean(title(p)) + " "

    for bad in rule.get("exclude_any", []):
        if bad in text:
            return -1

    score = 0
    for good in rule.get("must_any", []):
        if good in text:
            score += 1

    return score


def is_category_relevant(p, category):
    return category_relevance_score(p, category) > 0


def valid(p, category):
    return (
        p.get("category") == category
        and p.get("price_ready") is True
        and str(p.get("availability") or "").lower() == "available"
        and platform(p) in PLATFORMS
        and price(p) > 0
        and bool(title(p))
    )
def title_tokens(p):
    brand_tokens = set(clean(brand(p)).split())
    toks = set(clean(title(p)).split())

    return {
        x for x in toks
        if x not in GENERIC_MODEL_WORDS
        and x not in brand_tokens
        and len(x) > 1
    }


def title_similarity(a, b):
    aa = title_tokens(a)
    bb = title_tokens(b)

    if not aa or not bb:
        return 0.0

    return len(aa & bb) / len(aa | bb)



def comparison_tokens(p):
    raw = title(p).lower().split("|")[0]
    raw = re.sub(r"[^a-z0-9]+", " ", raw)
    b_tokens = set(clean(brand(p)).split())

    stop = {
        "smartphone","smart","phone","mobile","android","with","the",
        "new","latest","official","5g","4g","gb","tb","ram","storage",
        "mah","inch","online","buy","sale","original"
    }

    out = []
    for tok in raw.split():
        if tok in b_tokens or tok in stop:
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?(?:gb|tb|mah|hz|w|inch|cm)", tok):
            continue
        if tok in {"black","white","blue","green","red","grey","gray",
                   "silver","gold","pink","purple","orange","yellow",
                   "titanium","navy","brown","violet","indus"}:
            continue
        out.append(tok)

    return out[:12]


def shared_model_strength(a, b):
    ta = comparison_tokens(a)
    tb = comparison_tokens(b)

    if not ta or not tb:
        return 0.0, set()

    common = set(ta) & set(tb)
    if not common:
        return 0.0, set()

    # Strong signal: shared alphanumeric model tokens.
    model_common = {
        x for x in common
        if re.search(r"[a-z]", x) and re.search(r"\d", x)
    }

    # Numeric model token such as iPhone 15 / Galaxy S25.
    numeric_common = {
        x for x in common
        if re.fullmatch(r"[a-z]*\d{2,4}[a-z]*", x)
    }

    union = set(ta) | set(tb)
    jaccard = len(common) / len(union) if union else 0.0

    score = jaccard

    if model_common:
        score += 0.45

    elif numeric_common:
        score += 0.35

    return min(score, 1.0), common

def normalize_capacity(value):
    """
    Normalize capacities to GB so 1024GB and 1TB compare consistently.
    """
    v = clean(value)
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(gb|tb)", v)

    if not m:
        return ""

    amount = float(m.group(1))

    if m.group(2) == "tb":
        amount *= 1024

    if amount.is_integer():
        return str(int(amount)) + "gb"

    return f"{amount:g}gb"


def variant_parts(p):
    return {
        "ram": normalize_capacity(spec_value(p, ("ram",))),
        "storage": normalize_capacity(
            spec_value(p, ("storage", "rom"))
        ),
    }


def variants_compatible(products_for_model, category):
    """
    Variant validation.

    Memory-sensitive categories:
      - storage known on at least 2 platforms and equal
      - RAM, when exposed, must be known on at least 2 platforms and equal

    Other categories:
      - exact brand + model identity is sufficient
    """
    if category not in MEMORY_VARIANT_CATEGORIES:
        return True

    parts = [variant_parts(p) for p in products_for_model]

    known_storage = [
        x["storage"] for x in parts
        if x["storage"]
    ]

    known_ram = [
        x["ram"] for x in parts
        if x["ram"]
    ]

    if len(known_storage) < 2:
        return False

    if len(set(known_storage)) != 1:
        return False

    if known_ram:
        if len(known_ram) < 2:
            return False

        if len(set(known_ram)) != 1:
            return False

    return True


def inferred_variant(products_for_model):
    parts = [variant_parts(p) for p in products_for_model]

    storage = next(
        (x["storage"] for x in parts if x["storage"]),
        ""
    )
    ram = next(
        (x["ram"] for x in parts if x["ram"]),
        ""
    )

    return {
        "ram": ram,
        "storage": storage,
    }


def pretty_model(model):
    text = str(model or "").strip()

    replacements = [
        (r"\bpro plus\b", "Pro+"),
        (r"\bplus\b", "+"),
        (r"\bfe\b", "FE"),
        (r"\bultra\b", "Ultra"),
        (r"\bmax\b", "Max"),
        (r"\bmini\b", "Mini"),
        (r"\blite\b", "Lite"),
        (r"\bpro\b", "Pro"),
        (r"\bnote\b", "Note"),
        (r"\bgalaxy\b", "Galaxy"),
        (r"\biphone\b", "iPhone"),
        (r"\bnord\b", "Nord"),
        (r"\bpixel\b", "Pixel"),
        (r"\brealme\b", "realme"),
    ]

    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.I)

    return re.sub(
        r"\b([a-z]{1,3})(\d+[a-z0-9]*)\b",
        lambda m: m.group(1).title() + m.group(2).upper(),
        text
    )


def product_payload(p):
    return {
        "product_id": str(
            p.get("product_id")
            or p.get("id")
            or p.get("asin")
            or p.get("_id")
            or p.get("product_url")
            or ""
        ),
        "title": title(p),
        "brand": brand(p),
        "price_inr": round(price(p), 2),
        "rating": (
            p.get("average_rating")
            if p.get("average_rating") not in (None, "")
            else p.get("rating")
        ),
        "image_url": p.get("main_image") or p.get("image") or "",
        "product_url": p.get("product_url") or "",
        "platform": platform(p),
        "category": p.get("category") or "",
        "specifications": p.get("specifications") or {},
        "model_signature": model_signature(p),
    }


def choose_model_groups(candidates, category, limit=PRODUCTS_PER_AD):
    """
    Pick distinct model groups while explicitly maximizing platform diversity
    and excluding obvious accessory/irrelevant products.
    """
    filtered = [
        p for p in candidates
        if is_category_relevant(p, category)
    ]

    groups = defaultdict(list)

    for p in filtered:
        key = (
            model_signature(p),
            spec_value(p, ("ram",))
            if category in MEMORY_VARIANT_CATEGORIES else "",
            spec_value(p, ("storage", "rom"))
            if category in MEMORY_VARIANT_CATEGORIES else "",
        )

        if key[0]:
            groups[key].append(p)

    group_items = list(groups.items())

    # Strong groups first, but favor groups that add platform coverage.
    group_items.sort(
        key=lambda kv: (
            len({platform(x) for x in kv[1]}),
            max(category_relevance_score(x, category) for x in kv[1]),
            max(rating_num(x) for x in kv[1]),
            -min(price(x) for x in kv[1]),
        ),
        reverse=True,
    )

    selected = []
    used_platforms = set()

    # Pass 1: deliberately acquire missing platforms.
    for _, items in group_items:
        if len(selected) >= limit:
            break

        best = sorted(
            items,
            key=lambda x: (
                platform(x) in used_platforms,
                -category_relevance_score(x, category),
                -rating_num(x),
                price(x),
            )
        )[0]

        if platform(best) not in used_platforms:
            selected.append(best)
            used_platforms.add(platform(best))

    # Pass 2: fill remaining slots with new models and strong relevance.
    for _, items in group_items:
        if len(selected) >= limit:
            break

        if any(
            model_signature(existing) == next(iter(
                [model_signature(items[0])]
            ))
            for existing in selected
        ):
            continue

        best = sorted(
            items,
            key=lambda x: (
                -category_relevance_score(x, category),
                -rating_num(x),
                price(x),
                platform(x),
            )
        )[0]

        selected.append(best)

    return selected[:limit]


def all_platforms(items):
    return {platform(x) for x in items}


def has_min_platforms(items, minimum=MIN_PLATFORMS_FOR_RECOMMENDATION):
    return len(all_platforms(items)) >= minimum


def load_docs(category):
    query = {
        "category": category,
        "price_ready": True,
        "availability": "available",
        "platform": {"$in": list(PLATFORMS)},
    }

    projection = {
        "product_id": 1,
        "id": 1,
        "asin": 1,
        "_id": 1,
        "title": 1,
        "brand": 1,
        "price": 1,
        "price_inr": 1,
        "average_rating": 1,
        "rating": 1,
        "main_image": 1,
        "image": 1,
        "product_url": 1,
        "platform": 1,
        "category": 1,
        "specifications": 1,
        "price_ready": 1,
        "availability": 1,
    }

    cursor = products.find(query, projection)

    if MONGO_LIMIT:
        cursor = cursor.limit(MONGO_LIMIT)

    raw = list(cursor)

    return [x for x in raw if valid(x, category)]
def budget_targets(category):
    return BUDGET_TARGETS.get(
        category,
        [5000, 10000, 15000, 20000, 30000, 50000]
    )


def build_budget_ads(docs, category):
    ads = []
    display = CATEGORY_DISPLAY.get(
        category,
        category.replace("-", " ").title()
    )

    for budget in budget_targets(category):
        candidates = [
            x for x in docs
            if price(x) <= budget
            and is_category_relevant(x, category)
        ]

        candidates.sort(
            key=lambda x: (
                abs(price(x) - budget),
                -category_relevance_score(x, category),
                -rating_num(x),
            )
        )

        selected = choose_model_groups(
            candidates,
            category,
        )

        if len(selected) < 3:
            continue

        selected_platforms = all_platforms(selected)

        if len(selected_platforms) < MIN_PLATFORMS_FOR_RECOMMENDATION:
            continue

        ads.append({
            "ad_type": "budget_recommendation",
            "category": category,
            "headline": (
                f"Best {display} Under ₹{budget:,}"
            ),
            "budget_inr": budget,
            "platforms": sorted(selected_platforms),
            "products": [product_payload(x) for x in selected],
        })

        if len(ads) >= MAX_BUDGET_ADS:
            break

    return ads

