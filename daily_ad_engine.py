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
    specs = p.get("specifications") or {}
    normalized = {
        clean(k): clean(v)
        for k, v in specs.items()
        if v not in (None, "")
    }

    for wanted in names:
        wanted = clean(wanted)
        for key, value in normalized.items():
            if key == wanted or wanted in key:
                return value

    t = clean(title(p))

    if "ram" in wanted:
        m = re.search(r"\b(\d{1,3})\s*gb\s*ram\b", t)
        if m:
            return m.group(1) + "gb"
    else:
        m = re.search(r"\b(\d{1,4})\s*(gb|tb)\s*(?:storage|rom)\b", t)
        if m:
            return m.group(1) + m.group(2)

    return ""


def model_signature(p):
    """
    Extracts an actual smartphone model identifier.

    Strong examples:
      S25 FE -> s25 fe
      K14x   -> k14x
      16T    -> 16t
      2a     -> 2a
      iPhone 15 -> 15
    """

    raw = title(p).lower()
    raw = raw.split("|")[0]
    raw = re.sub(r"[^a-z0-9]+", " ", raw)
    tokens = raw.split()

    candidates = []

    for i, token in enumerate(tokens):
        if token in GENERIC_MODEL_WORDS:
            continue

        # Alphanumeric model code containing letters + digits.
        if re.fullmatch(r"(?=.*[a-z])(?=.*\d)[a-z0-9]{2,10}", token):
            candidates.append(token)

            if i + 1 < len(tokens):
                nxt = tokens[i + 1]
                if nxt in MODEL_SUFFIX_WORDS:
                    candidates.append(nxt)
            continue

        # Pure model number such as iPhone 15 / S24.
        if re.fullmatch(r"\d{2,4}", token):
            candidates.append(token)

            if i + 1 < len(tokens):
                nxt = tokens[i + 1]
                if nxt in MODEL_SUFFIX_WORDS:
                    candidates.append(nxt)

    if candidates:
        return " ".join(dict.fromkeys(candidates[:3]))

    # Fallback for unusual products with no numeric model.
    brand_tokens = set(clean(brand(p)).split())
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


def compatible_specs(a, b):
    for wanted in (("ram",), ("storage", "rom")):
        av = spec_value(a, wanted)
        bv = spec_value(b, wanted)

        if av and bv and av != bv:
            return False

    return True


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
    groups = defaultdict(lambda: defaultdict(list))

    for p in docs:
        b = normalize_brand(p)
        mk = model_signature(p)

        if b and mk:
            groups[(b, mk)][platform(p)].append(p)

    candidates = []

    for (b, mk), by_platform in groups.items():

        if not all(pf in by_platform for pf in PLATFORMS):
            continue

        # Pick one candidate per platform, preferring lower price
        # but only after checking compatibility.
        selected = {}

        for pf in PLATFORMS:
            selected[pf] = min(
                by_platform[pf],
                key=lambda x: (price(x), -rating_num(x))
            )

        if not all(
            compatible_specs(selected["amazon"], selected[pf])
            for pf in ("flipkart", "croma")
        ):
            continue

        similarities = [
            title_similarity(selected["amazon"], selected["flipkart"]),
            title_similarity(selected["amazon"], selected["croma"]),
        ]

        if max(similarities) < 0.35:
            continue

        prices = {
            pf: price(selected[pf])
            for pf in PLATFORMS
        }

        low = min(prices.values())
        high = max(prices.values())

        if low <= 0:
            continue

        spread_pct = ((high - low) / high) * 100

        # Reject obvious false matches.
        if spread_pct > MAX_COMPARISON_SPREAD_PCT:
            continue

        saving = high - low

        if (saving / high) * 100 < MIN_COMPARISON_SAVING_PCT:
            continue

        candidates.append({
            "brand": brand(selected["amazon"]),
            "model": mk,
            "selected": selected,
            "prices": prices,
            "spread_pct": round(spread_pct, 2),
            "saving": round(saving, 2),
            "saving_pct": round((saving / high) * 100, 2),
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

        selected = item["selected"]

        ads.append({
            "ad_type": "price_comparison",
            "category": CATEGORY,
            "brand": item["brand"],
            "model": item["model"],
            "headline": f"Compare {item['brand']} {item['model']}",
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
        "engine": "daily_ad_engine_test_v2",
        "category": CATEGORY,
        "platforms_required": list(PLATFORMS),
        "rules": {
            "budget_ads": "unique models; minimum 2 platforms",
            "brand_ads": "safe brand; unique models; minimum 2 platforms",
            "comparison_ads": "same model; all 3 platforms; spec compatibility; <=35% price spread",
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
    print("TRUSTFOLIO DAILY AD ENGINE - SMARTPHONES TEST V2")
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
