import json, os, re
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

BASE = Path.home() / "new_scraper"
OUT = BASE / "ads" / "daily_ad_test.json"

CATEGORY = "smart-phones"
PLATFORMS = ("amazon", "flipkart", "croma")

MAX_BUDGET_ADS = 3
MAX_BRAND_ADS = 3
MAX_COMPARISON_ADS = 3
PRODUCTS_PER_AD = 5

MIN_PLATFORMS_FOR_RECOMMENDATION = 2
MIN_COMPARISON_SAVING_PCT = 2.0
MAX_COMPARISON_SPREAD_PCT = 35.0
MONGO_LIMIT = 5000

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
    "neo", "power", "edge", "prime", "play", "note"
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


def spec_value(p, names):
    """
    Return a normalized RAM/storage value.

    The function uses structured specifications first and then title parsing.
    For storage, titles such as "128 GB", "128GB Storage", and "2 TB"
    are supported.
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
                return clean(value)

    t = title(p).lower()

    if is_ram:
        m = re.search(r"\b(\d{1,3})\s*(gb|tb)\s*ram\b", t)
        if m:
            return m.group(1) + m.group(2)

        return ""

    # Explicit storage / ROM wording.
    m = re.search(
        r"\b(\d{1,4})\s*(gb|tb)\s*(?:storage|rom)\b",
        t
    )
    if m:
        return m.group(1) + m.group(2)

    # Otherwise use standalone GB/TB capacities, excluding the RAM
    # capacity when an explicit RAM value exists.
    capacities = list(
        re.finditer(r"\b(\d{1,4})\s*(gb|tb)\b", t)
    )

    ram_match = re.search(
        r"\b(\d{1,3})\s*(gb|tb)\s*ram\b",
        t
    )

    for m in capacities:
        value = m.group(1) + m.group(2)

        if ram_match and m.start() == ram_match.start():
            continue

        return value

    return ""


def model_signature(p):
    """
    Extract a conservative smartphone model identity.

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


def valid(p):
    return (
        p.get("category") == CATEGORY
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
    unit = m.group(2)

    if unit == "tb":
        amount *= 1024

    if amount.is_integer():
        return str(int(amount)) + "gb"

    return f"{amount:g}gb"


def variant_parts(p):
    """
    Return individually detectable variant fields.

    Empty means the source did not expose that field clearly.
    Missing information is treated as UNKNOWN, not as a mismatch.
    """
    return {
        "ram": normalize_capacity(spec_value(p, ("ram",))),
        "storage": normalize_capacity(
            spec_value(p, ("storage", "rom"))
        ),
    }


def variants_compatible(products_for_model):
    """
    Compare RAM/storage across a candidate cross-platform product set.

    Rules:
      - If a value is known on multiple platforms, every known value
        must agree.
      - Missing values are allowed.
      - Storage must be known on at least two platforms so we have
        meaningful evidence that the exact storage variant matches.
      - If RAM is known on multiple platforms, it must also agree.
    """
    parts = [variant_parts(p) for p in products_for_model]

    known_storage = [
        x["storage"] for x in parts if x["storage"]
    ]
    known_ram = [
        x["ram"] for x in parts if x["ram"]
    ]

    if len(known_storage) < 2:
        return False

    if len(set(known_storage)) != 1:
        return False

    if known_ram and len(set(known_ram)) != 1:
        return False

    return True


def inferred_variant(products_for_model):
    """
    Build the best available variant identity from agreeing source data.
    """
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
    """
    Human-friendly model text for the ad headline.
    """
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
    ]

    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.I)

    return text


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
        "category": CATEGORY,
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


def load_docs():
    query = {
        "category": CATEGORY,
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

    raw = list(products.find(query, projection).limit(MONGO_LIMIT))
    return [x for x in raw if valid(x)]


def budget_targets():
    # Useful consumer-facing budget bands.
    # We only keep bands for which at least 2 platforms have
    # eligible products under the budget.
    return [10000, 15000, 20000, 25000, 30000, 40000, 50000, 75000, 100000]


def build_budget_ads(docs):
    ads = []

    for budget in budget_targets():

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

        # Prefer 3 platforms; 2 is acceptable when data doesn't
        # provide all three.
        ads.append({
            "ad_type": "budget_recommendation",
            "category": CATEGORY,
            "headline": f"Best Smartphones Under ₹{budget:,}",
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


def build_brand_ads(docs):
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
                spec_value(p, ("ram",)),
                spec_value(p, ("storage", "rom")),
            )

            if key[0]:
                groups[key].append(p)

        if len(groups) < 3:
            continue

        pfs = {platform(x) for x in items}

        if len(pfs) < 2:
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

    for b, items, groups in brand_candidates:

        # Target around the median brand price.
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
            "category": CATEGORY,
            "brand": display_brand,
            "headline": f"Best {display_brand} Smartphones Under ₹{round(target):,}",
            "budget_inr": round(target),
            "platforms": sorted(all_platforms(selected)),
            "products": [product_payload(x) for x in selected],
        })

        if len(ads) >= MAX_BRAND_ADS:
            break

    return ads


def build_comparison_ads(docs):
    """
    Cross-platform same-product comparison with strict model matching
    and conservative variant matching.

    Important:
      - Exact model identity is mandatory.
      - Pro vs Pro+ remains different.
      - If RAM/storage are known on multiple platforms, values must match.
      - Missing RAM on one platform is allowed when the other platforms
        establish the same RAM.
      - Storage must be known and identical on at least two platforms.
      - All three platforms are required.
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

        # Try candidate combinations because a platform can contain
        # multiple variants of the same model.
        best_combo = None
        best_key = None

        for a in by_pf["amazon"]:
            for f in by_pf["flipkart"]:
                for c in by_pf["croma"]:

                    combo = [a, f, c]

                    if not variants_compatible(combo):
                        continue

                    prices = {
                        "amazon": price(a),
                        "flipkart": price(f),
                        "croma": price(c),
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

                    variant = inferred_variant(combo)

                    # Prefer:
                    # 1. More complete RAM/storage evidence
                    # 2. Better price saving
                    # 3. Better average rating
                    completeness = sum(
                        bool(variant_parts(x)["ram"])
                        for x in combo
                    ) + sum(
                        bool(variant_parts(x)["storage"])
                        for x in combo
                    )

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

        a, f, c = best_combo

        prices = {
            "amazon": price(a),
            "flipkart": price(f),
            "croma": price(c),
        }

        low = min(prices.values())
        high = max(prices.values())
        spread_pct = ((high - low) / high) * 100
        saving = high - low
        saving_pct = (saving / high) * 100
        variant = inferred_variant(best_combo)

        candidates.append({
            "brand": brand(a),
            "model": model,
            "variant": variant,
            "amazon": a,
            "flipkart": f,
            "croma": c,
            "prices": prices,
            "spread_pct": round(spread_pct, 2),
            "saving": round(saving, 2),
            "saving_pct": round(saving_pct, 2),
            "score": 1.0,
        })

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

        variant_parts_text = []
        if item["variant"]["ram"]:
            variant_parts_text.append(
                item["variant"]["ram"].upper()
            )
        if item["variant"]["storage"]:
            variant_parts_text.append(
                item["variant"]["storage"].upper()
            )

        variant_text = " ".join(variant_parts_text)

        headline = f"Compare {item['brand']} {display_model}"
        if variant_text:
            headline += f" {variant_text}"

        ads.append({
            "ad_type": "price_comparison",
            "category": CATEGORY,
            "brand": item["brand"],
            "model": item["model"],
            "variant": item["variant"],
            "headline": headline,
            "platforms": list(PLATFORMS),
            "prices": item["prices"],
            "best_platform": min(
                item["prices"],
                key=item["prices"].get
            ),
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
    docs = load_docs()
    counts = Counter(platform(x) for x in docs)

    budget_ads = build_budget_ads(docs)
    brand_ads = build_brand_ads(docs)
    comparison_ads = build_comparison_ads(docs)

    ads = budget_ads + brand_ads + comparison_ads

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
        "engine": "daily_ad_engine_test_v4",
        "category": CATEGORY,
        "platforms_required": list(PLATFORMS),
        "rules": {
            "budget_ads": "unique models; minimum 2 platforms",
            "brand_ads": "safe brand; unique models; minimum 2 platforms",
            "comparison_ads": "exact brand + model; matching known RAM/storage; storage verified on 2+ platforms; all 3 platforms; <=35% price spread",
        },
        "stats": {
            "eligible_products": len(docs),
            "platform_counts": dict(counts),
            "budget_ads": len(budget_ads),
            "brand_ads": len(brand_ads),
            "comparison_ads": len(comparison_ads),
            "total_ads": len(ads),
        },
        "ads": ads,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 78)
    print("TRUSTFOLIO DAILY AD ENGINE - SMARTPHONES TEST V4")
    print("=" * 78)
    print("Eligible products:", len(docs))
    print("Platform counts  :", dict(counts))
    print("Budget ads       :", len(budget_ads))
    print("Brand ads        :", len(brand_ads))
    print("Comparison ads   :", len(comparison_ads))
    print("TOTAL ADS        :", len(ads))
    print("OUTPUT           :", OUT)
    print("=" * 78)


if __name__ == "__main__":
    try:
        main()
    finally:
        client.close()
