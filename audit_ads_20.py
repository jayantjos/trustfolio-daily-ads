import json
import re
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path.home() / "new_scraper"
INPUT = BASE / "ads" / "daily_ads_20_categories.json"

PLATFORMS = {"amazon", "flipkart", "croma"}

GENERIC_BRANDS = {
    "add", "ai", "android", "bluetooth", "computer", "desktop",
    "earbuds", "good", "in ear", "kids", "mobile", "phone",
    "portable", "smart", "tablet", "truly", "wireless",
    "10", "10 1", "2025", "7",
}

SELLER_WORDS = {
    "store", "shop", "online", "seller", "trader", "traders",
    "retail", "retailer", "hub", "mart", "enterprise", "enterprises",
    "world", "deals", "official store",
}

CATEGORY_TERMS = {
    "smartwatches": ["watch", "smartwatch"],
    "headphones-earbuds": ["headphone", "earbud", "buds", "headset"],
    "speakers": ["speaker", "soundbar", "home theatre", "home theater"],
    "ceiling-fans": ["fan"],
    "water-purifiers": ["purifier"],
    "mixer-grinders": ["mixer", "grinder", "juicer"],
    "drones": ["drone"],
    "desktop-computers": ["desktop", "computer", "pc"],
    "geysers": ["geyser", "water heater"],
    "laptops": ["laptop", "notebook"],
    "smart-phones": ["smartphone", "phone", "mobile"],
    "refrigerators": ["refrigerator", "fridge"],
    "smart-tvs": ["tv", "television"],
    "air-coolers": ["air cooler", "cooler"],
    "vacuum-cleaners": ["vacuum", "robot vacuum", "cleaner"],
    "air-conditioners": ["air conditioner", "ac", "split ac"],
    "induction-cooktops": ["induction", "cooktop"],
    "washing-machines": ["washing machine", "washer"],
    "tablets": ["tablet"],
    "microwave-ovens": ["microwave", "oven"],
}


def clean(x):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(x or "").lower())).strip()


def flags_for_brand(brand):
    b = clean(brand)
    flags = []

    if not b:
        flags.append("BLANK_BRAND")

    if b in GENERIC_BRANDS:
        flags.append("GENERIC_BRAND")

    if any(word in b.split() for word in SELLER_WORDS):
        flags.append("SELLER_LIKE_BRAND")

    if len(b) < 3:
        flags.append("SHORT_BRAND")

    if re.fullmatch(r"[\d\s.+-]+", b or ""):
        flags.append("NUMERIC_BRAND")

    return flags


def category_match(category, title):
    terms = CATEGORY_TERMS.get(category, [])
    t = clean(title)
    return any(term in t for term in terms)


def product_platforms(products):
    return {
        str(p.get("platform") or "").strip().lower()
        for p in products
        if p.get("platform")
    }


def inspect_products(ad):
    products = ad.get("products") or []
    flags = []
    pfs = []
    for p in products:
        pf = str(p.get("platform") or "").strip().lower()
        pfs.append(pf)

        if pf not in PLATFORMS:
            flags.append(f"UNKNOWN_PLATFORM:{pf}")

        if not category_match(ad.get("category", ""), p.get("title", "")):
            flags.append(f"CATEGORY_TITLE_MISMATCH:{pf}")

    if len(set(pfs)) < 2:
        flags.append("ONLY_ONE_PLATFORM")

    if set(pfs) != PLATFORMS:
        flags.append("MISSING_PLATFORM")

    prices = [float(p.get("price_inr") or 0) for p in products]
    if any(x <= 0 for x in prices):
        flags.append("BAD_PRICE")

    if len(products) < 3:
        flags.append("LESS_THAN_3_PRODUCTS")

    return flags


def budget_audit(ad):
    flags = []
    flags.extend(inspect_products(ad))

    budget = float(ad.get("budget_inr") or 0)

    prices = [
        float(p.get("price_inr") or 0)
        for p in ad.get("products", [])
    ]

    if prices and max(prices) > budget:
        flags.append("PRODUCT_OVER_BUDGET")

    if len(set(
        clean(p.get("model_signature"))
        for p in ad.get("products", [])
    )) != len(ad.get("products", [])):
        flags.append("DUPLICATE_MODEL_SIGNATURE")

    return flags


def brand_audit(ad):
    flags = []
    flags.extend(inspect_products(ad))
    flags.extend(flags_for_brand(ad.get("brand")))

    brand_value = clean(ad.get("brand"))
    category = ad.get("category", "")

    for p in ad.get("products", []):
        p_brand = clean(p.get("brand"))
        title = clean(p.get("title"))

        if p_brand and brand_value and p_brand != brand_value:
            flags.append("PRODUCT_BRAND_MISMATCH")

        if brand_value and brand_value not in title:
            flags.append("BRAND_NOT_IN_TITLE")

        if not category_match(category, p.get("title", "")):
            flags.append("CATEGORY_TITLE_MISMATCH")

    return sorted(set(flags))


def main():
    if not INPUT.exists():
        raise SystemExit(f"Missing: {INPUT}")

    data = json.loads(INPUT.read_text(encoding="utf-8"))
    ads = data.get("ads", [])

    budget_ads = [a for a in ads if a.get("ad_type") == "budget_recommendation"]
    brand_ads = [a for a in ads if a.get("ad_type") == "brand_recommendation"]

    print("=" * 100)
    print("TRUSTFOLIO BUDGET + BRAND AD AUDIT")
    print("=" * 100)
    print("Budget ads:", len(budget_ads))
    print("Brand ads :", len(brand_ads))
    print()

    budget_flagged = []
    brand_flagged = []

    for i, ad in enumerate(budget_ads, 1):
        flags = sorted(set(budget_audit(ad)))
        if flags:
            budget_flagged.append((i, ad, flags))

    for i, ad in enumerate(brand_ads, 1):
        flags = brand_audit(ad)
        if flags:
            brand_flagged.append((i, ad, flags))

    print("BUDGET FLAGGED:", len(budget_flagged))
    for i, ad, flags in budget_flagged:
        print(f"\nBUDGET #{i} | {ad.get('category')} | {ad.get('headline')}")
        print("FLAGS:", ", ".join(flags))
        print("PLATFORMS:", ad.get("platforms"))
        for p in ad.get("products", []):
            print(
                " -",
                p.get("platform"),
                "|",
                p.get("title"),
                "| ₹",
                p.get("price_inr"),
            )

    print("\n" + "=" * 100)
    print("BRAND FLAGGED:", len(brand_flagged))

    for i, ad, flags in brand_flagged:
        print(f"\nBRAND #{i} | {ad.get('category')} | {ad.get('headline')}")
        print("BRAND:", ad.get("brand"))
        print("FLAGS:", ", ".join(flags))
        print("PLATFORMS:", ad.get("platforms"))
        for p in ad.get("products", []):
            print(
                " -",
                p.get("platform"),
                "|",
                p.get("brand"),
                "|",
                p.get("title"),
                "| ₹",
                p.get("price_inr"),
            )

    print("\n" + "=" * 100)

    category_counts = Counter(
        a.get("category")
        for a in brand_ads
        if a.get("category")
    )

    suspicious_brand_values = Counter(
        clean(a.get("brand"))
        for a in brand_ads
        if flags_for_brand(a.get("brand"))
    )

    print("BRAND ADS BY CATEGORY:")
    for category, count in sorted(category_counts.items()):
        print(f"  {category:22} {count}")

    print("\nSUSPICIOUS BRAND VALUES:")
    if suspicious_brand_values:
        for value, count in suspicious_brand_values.most_common():
            print(f"  {value!r:30} {count}")
    else:
        print("  NONE")

    print("=" * 100)


if __name__ == "__main__":
    main()
