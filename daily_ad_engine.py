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


def extract_capacities(value):
    text = clean(value)
    return [
        amount + unit
        for amount, unit in re.findall(r"\b(\d{1,4})\s*(gb|tb)\b", text)
    ]


def spec_value(p, names):
    """
    Normalize RAM/storage from structured specs or product title.

    Handles:
      4GB RAM, 128GB Storage
      6+128GB
      6GB+128GB
      6/128GB
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
                return clean(value)

    t = title(p).lower()

    combined = re.search(
        r"\b(\d{1,3})\s*(gb|tb)?\s*(?:\+|/)\s*"
        r"(\d{1,4})\s*(gb|tb)\b",
        t
    )

    if is_ram:
        if combined:
            return combined.group(1) + (combined.group(2) or combined.group(4))

        m = re.search(r"\b(\d{1,3})\s*(gb|tb)\s*ram\b", t)
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
    ram_match = re.search(r"\b(\d{1,3})\s*(gb|tb)\s*ram\b", t)

    for capacity in capacities:
        if ram_match:
            ram_capacity = ram_match.group(1) + ram_match.group(2)
            if capacity == ram_capacity:
                continue
        return capacity

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
        "engine": "daily_ad_engine_test_v6",
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
    print("TRUSTFOLIO DAILY AD ENGINE - SMARTPHONES TEST V6")
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
