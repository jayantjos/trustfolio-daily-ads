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

GENERIC_MODEL_WORDS = {
    "smartphone", "smart", "phone", "mobile", "android",
    "with", "the", "new", "latest", "official", "5g", "4g",
    "gb", "tb", "ram", "storage", "mah"
}

MODEL_SUFFIX_WORDS = {
    "fe", "pro", "plus", "max", "mini", "lite", "ultra",
    "neo", "power", "edge", "prime", "play", "note", "se"
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


def choose_model_groups(candidates, limit=PRODUCTS_PER_AD):
    """
    Picks distinct model groups, while maximizing platform coverage.
    """

    groups = defaultdict(list)

    for p in candidates:
        key = (
            model_signature(p),
            spec_value(p, ("ram",)),
            spec_value(p, ("storage", "rom")),
        )
        if key[0]:
            groups[key].append(p)

    group_items = list(groups.items())

    # First prefer groups that exist on more platforms.
    group_items.sort(
        key=lambda kv: (
            len({platform(x) for x in kv[1]}),
            max(rating_num(x) for x in kv[1]),
            -min(price(x) for x in kv[1]),
        ),
        reverse=True,
    )

    selected = []
    used_platforms = set()

    # Pass 1: get platform coverage.
    for _, items in group_items:
        if len(selected) >= limit:
            break

        available = sorted(
            items,
            key=lambda x: (
                platform(x) in used_platforms,
                -rating_num(x),
                price(x),
            )
        )

        pick = available[0]
        selected.append(pick)
        used_platforms.add(platform(pick))

    # Pass 2: additional unique models.
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
    display = CATEGORY_DISPLAY.get(category, category.replace("-", " ").title())

    for budget in budget_targets(category):
        candidates = [
            x for x in docs
            if price(x) <= budget
        ]

        candidates.sort(
            key=lambda x: (
                abs(price(x) - budget),
                -rating_num(x),
            )
        )

        selected = choose_model_groups(candidates)

        if len(selected) < 3:
            continue

        if not has_min_platforms(selected):
            continue

        ads.append({
            "ad_type": "budget_recommendation",
            "category": category,
            "headline": f"Best {display} Under ₹{budget:,}",
            "budget_inr": budget,
            "platforms": sorted(all_platforms(selected)),
            "products": [product_payload(x) for x in selected],
        })

        if len(ads) >= MAX_BUDGET_ADS:
            break

    return ads


def safe_brand(b):
    b = clean(b)
    return bool(
        b
        and b not in GENERIC_BRANDS
        and len(b) >= 2
        and not re.fullmatch(r"[\d\s.+-]+", b)
    )


def leading_brand(p):
    b = normalize_brand(p)
    t = clean(title(p))
    return bool(b and t and (t == b or t.startswith(b + " ")))


def build_brand_ads(docs, category):
    brand_docs = defaultdict(list)

    for p in docs:
        b = normalize_brand(p)
        if safe_brand(b) and leading_brand(p):
            brand_docs[b].append(p)

    brand_candidates = []

    for b, items in brand_docs.items():
        groups = defaultdict(list)

        for p in items:
            key = (
                model_signature(p),
                spec_value(p, ("ram",)) if category in MEMORY_VARIANT_CATEGORIES else "",
                spec_value(p, ("storage", "rom")) if category in MEMORY_VARIANT_CATEGORIES else "",
            )

            if key[0]:
                groups[key].append(p)

        if len(groups) < 3:
            continue

        if len({platform(x) for x in items}) < 2:
            continue

        brand_candidates.append((b, items, groups))

    brand_candidates.sort(
        key=lambda x: (
            len(x[2]),
            len({platform(p) for p in x[1]}),
        ),
        reverse=True,
    )

    ads = []
    display_category = CATEGORY_DISPLAY.get(
        category,
        category.replace("-", " ").title()
    )

    for b, items, groups in brand_candidates:
        all_prices = sorted(price(x) for x in items)
        target = all_prices[len(all_prices) // 2]

        candidates = [
            x for x in items
            if price(x) <= target * 1.10
        ]

        candidates.sort(
            key=lambda x: (
                abs(price(x) - target),
                -rating_num(x),
            )
        )

        selected = choose_model_groups(candidates)

        if len(selected) < 3:
            continue

        if not has_min_platforms(selected):
            continue

        display_brand = brand(selected[0]) or b.title()

        ads.append({
            "ad_type": "brand_recommendation",
            "category": category,
            "brand": display_brand,
            "headline": f"Best {display_brand} {display_category} Under ₹{round(target):,}",
            "budget_inr": round(target),
            "platforms": sorted(all_platforms(selected)),
            "products": [product_payload(x) for x in selected],
        })

        if len(ads) >= MAX_BRAND_ADS:
            break

    return ads


def build_comparison_ads(docs, category):
    """
    Cross-platform same-product comparison.

    Exact brand + model identity is mandatory.
    Memory-sensitive categories additionally require matching RAM/storage
    evidence. Other categories use exact model identity and price-spread
    protection.
    """
    by_brand_model = defaultdict(lambda: defaultdict(list))

    for p in docs:
        b = normalize_brand(p)
        model = model_signature(p)
        pf = platform(p)

        if b and model and pf in PLATFORMS:
            by_brand_model[(b, model)][pf].append(p)

    candidates = []

    for (b, model), by_pf in by_brand_model.items():
        if not all(pf in by_pf for pf in PLATFORMS):
            continue

        best_combo = None
        best_key = None

        for a in by_pf["amazon"]:
            for f in by_pf["flipkart"]:
                for croma_item in by_pf["croma"]:
                    combo = [a, f, croma_item]

                    if not variants_compatible(combo, category):
                        continue

                    prices = {
                        "amazon": price(a),
                        "flipkart": price(f),
                        "croma": price(croma_item),
                    }

                    if any(v <= 0 for v in prices.values()):
                        continue

                    low = min(prices.values())
                    high = max(prices.values())
                    spread_pct = ((high - low) / high) * 100

                    if spread_pct > MAX_COMPARISON_SPREAD_PCT:
                        continue

                    saving = high - low
                    saving_pct = (saving / high) * 100

                    if saving_pct < MIN_COMPARISON_SAVING_PCT:
                        continue

                    if category in MEMORY_VARIANT_CATEGORIES:
                        variant = inferred_variant(combo)
                        completeness = sum(
                            bool(variant_parts(x)["ram"])
                            + bool(variant_parts(x)["storage"])
                            for x in combo
                        )
                    else:
                        variant = {
                            "ram": "",
                            "storage": "",
                        }
                        completeness = 0

                    avg_rating = sum(
                        rating_num(x) for x in combo
                    )

                    key = (
                        completeness,
                        saving_pct,
                        avg_rating,
                    )

                    if best_combo is None or key > best_key:
                        best_combo = combo
                        best_key = key

        if best_combo is None:
            continue

        a, f, croma_item = best_combo

        prices = {
            "amazon": price(a),
            "flipkart": price(f),
            "croma": price(croma_item),
        }

        low = min(prices.values())
        high = max(prices.values())
        spread_pct = ((high - low) / high) * 100
        saving = high - low
        saving_pct = (saving / high) * 100

        if category in MEMORY_VARIANT_CATEGORIES:
            variant = inferred_variant(best_combo)
        else:
            variant = {"ram": "", "storage": ""}

        candidates.append({
            "brand": brand(a),
            "model": model,
            "variant": variant,
            "amazon": a,
            "flipkart": f,
            "croma": croma_item,
            "prices": prices,
            "spread_pct": round(spread_pct, 2),
            "saving": round(saving, 2),
            "saving_pct": round(saving_pct, 2),
            "score": 1.0,
        })

    # Avoid multiple ads for the same product identity.
    unique = {}
    for item in candidates:
        key = (
            normalize_brand(item["amazon"]),
            item["model"],
        )
        old = unique.get(key)
        if old is None or item["saving_pct"] > old["saving_pct"]:
            unique[key] = item

    candidates = list(unique.values())

    candidates.sort(
        key=lambda x: (
            x["saving_pct"],
            x["saving"],
        ),
        reverse=True,
    )

    ads = []

    for item in candidates[:MAX_COMPARISON_ADS]:
        selected = {
            "amazon": item["amazon"],
            "flipkart": item["flipkart"],
            "croma": item["croma"],
        }

        display_model = pretty_model(item["model"])
        headline = f"Compare {item['brand']} {display_model}"

        if category in MEMORY_VARIANT_CATEGORIES:
            variant_text = []
            if item["variant"]["ram"]:
                variant_text.append(item["variant"]["ram"].upper())
            if item["variant"]["storage"]:
                variant_text.append(item["variant"]["storage"].upper())

            if variant_text:
                headline += " " + " ".join(variant_text)

        ads.append({
            "ad_type": "price_comparison",
            "category": category,
            "brand": item["brand"],
            "model": item["model"],
            "variant": item["variant"],
            "headline": headline,
            "platforms": list(PLATFORMS),
            "prices": item["prices"],
            "best_platform": min(item["prices"], key=item["prices"].get),
            "best_price_inr": min(item["prices"].values()),
            "saving_inr": item["saving"],
            "saving_percent": item["saving_pct"],
            "price_spread_percent": item["spread_pct"],
            "match_score": item["score"],
            "products": {
                pf: product_payload(selected[pf])
                for pf in PLATFORMS
            },
        })

    return ads


def main():
    all_ads = []
    category_results = {}
    total_eligible = 0

    print("=" * 88)
    print("TRUSTFOLIO DAILY AD ENGINE - 20 CATEGORY TEST")
    print("=" * 88)
    print("Categories:", len(CATEGORIES))
    print("Platforms :", ", ".join(PLATFORMS))
    print()

    for category in CATEGORIES:
        docs = load_docs(category)
        counts = Counter(platform(x) for x in docs)

        budget_ads = build_budget_ads(docs, category)
        brand_ads = build_brand_ads(docs, category)
        comparison_ads = build_comparison_ads(docs, category)

        category_ads = budget_ads + brand_ads + comparison_ads
        all_ads.extend(category_ads)
        total_eligible += len(docs)

        category_results[category] = {
            "display_name": CATEGORY_DISPLAY.get(category, category),
            "eligible_products": len(docs),
            "platform_counts": dict(counts),
            "budget_ads": len(budget_ads),
            "brand_ads": len(brand_ads),
            "comparison_ads": len(comparison_ads),
            "total_ads": len(category_ads),
        }

        print(
            f"{category:22} | products={len(docs):5d} "
            f"| budget={len(budget_ads):2d} "
            f"| brand={len(brand_ads):2d} "
            f"| compare={len(comparison_ads):2d} "
            f"| total={len(category_ads):2d}"
        )

    output = {
        "brand": {
            "name": "Trustfolio",
            "website": "https://www.trustfolio.in",
            "app": "Trustfolio",
        },
        "generated_at": datetime.now().isoformat(),
        "source": "Trustfolio MongoDB",
        "generated_from_live_mongodb": True,
        "trustfolio_backend_unchanged": True,
        "engine": "daily_ad_engine_20_v2",
        "categories": CATEGORIES,
        "platforms_required": list(PLATFORMS),
        "rules": {
            "budget_ads": "unique models; minimum 2 platforms; category-specific consumer budget bands",
            "brand_ads": "safe brand; unique models; minimum 2 platforms",
            "comparison_ads": "exact brand + model; memory categories additionally match RAM/storage; all 3 platforms; <=35% price spread",
        },
        "stats": {
            "categories": len(CATEGORIES),
            "eligible_products_total": total_eligible,
            "budget_ads": sum(x["budget_ads"] for x in category_results.values()),
            "brand_ads": sum(x["brand_ads"] for x in category_results.values()),
            "comparison_ads": sum(x["comparison_ads"] for x in category_results.values()),
            "total_ads": len(all_ads),
            "categories_with_ads": sum(
                1 for x in category_results.values()
                if x["total_ads"] > 0
            ),
        },
        "category_results": category_results,
        "ads": all_ads,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("=" * 88)
    print("TOTAL ELIGIBLE PRODUCTS:", total_eligible)
    print("TOTAL BUDGET ADS       :", output["stats"]["budget_ads"])
    print("TOTAL BRAND ADS        :", output["stats"]["brand_ads"])
    print("TOTAL COMPARISON ADS   :", output["stats"]["comparison_ads"])
    print("TOTAL ADS              :", output["stats"]["total_ads"])
    print("CATEGORIES WITH ADS    :", output["stats"]["categories_with_ads"])
    print("OUTPUT                 :", OUT)
    print("=" * 88)


if __name__ == "__main__":
    try:
        main()
    finally:
        client.close()
