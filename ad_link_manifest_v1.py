#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from campaign_link_contract_v1 import campaign_link

BASE = Path.home() / "new_scraper"
CONFIG_PATH = BASE / "ads" / "creative_config_v1.json"
DEFAULT_INPUT = BASE / "ads" / "daily_ads_20_categories_v8.json"
DEFAULT_OUTPUT = BASE / "ads" / "creative_ad_manifest_v1.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def stable_ad_id(index: int, ad: dict) -> str:
    category = str(ad.get("category") or "unknown")
    ad_type = str(ad.get("ad_type") or "ad")
    budget = str(ad.get("budget_inr") or "")
    brand = str(ad.get("brand") or "")
    model = str(ad.get("model") or "")
    raw = "|".join([category, ad_type, budget, brand, model])
    import hashlib
    return "tf-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def build_manifest(data: dict, config: dict) -> dict:
    ads = []

    for index, ad in enumerate(data.get("ads", []), start=1):
        ad_id = stable_ad_id(index, ad)
        category = ad.get("category") or ""
        ad_type = ad.get("ad_type") or ""

        link = campaign_link(ad, config, ad_id)
        landing_url = link["landing_url"]

        products = []
        raw_products = ad.get("products") or []

        # Budget/brand ads store products as a list.
        # Price-comparison ads store products as a platform-keyed dict:
        # {"amazon": {...}, "flipkart": {...}, "croma": {...}}.
        if isinstance(raw_products, dict):
            iterable = raw_products.items()
        elif isinstance(raw_products, list):
            iterable = ((None, product) for product in raw_products)
        else:
            iterable = ()

        for platform_key, product in iterable:
            if not isinstance(product, dict):
                continue

            product_copy = dict(product)

            if platform_key:
                product_copy["comparison_platform"] = platform_key

            # Current safe behavior: each product/card points to the
            # TrustFolio category landing page. Product-specific deep links
            # stay disabled until a real TrustFolio product route exists.
            product_copy["click_url"] = landing_url
            product_copy["ad_rank"] = len(products) + 1
            product_copy["product_deep_link"] = None
            products.append(product_copy)

        ads.append({
            "ad_id": ad_id,
            "ad_type": ad_type,
            "category": category,
            "headline": ad.get("headline") or "",
            "brand": ad.get("brand") or "",
            "model": ad.get("model") or "",
            "budget_inr": ad.get("budget_inr"),
            "platforms": ad.get("platforms") or [],
            "landing_url": landing_url,
            "requested_filters": link["requested_filters"],
            "prefill_ready": link["prefill_ready"],
            "verified_prefill_fields": link["verified_prefill_fields"],
            "unverified_prefill_fields": link["unverified_prefill_fields"],
            "site_ranking_status": link["site_ranking_status"],
            "click_destination": link["click_destination"],
            "website_url": config["brand"]["website_url"],
            "play_store_url": config["brand"]["play_store_url"],
            "fixed_branding": {
                "brand_name": config["brand"]["name"],
                "tagline": config["brand"]["tagline"],
                "website": config["brand"]["website_url"],
                "play_store": config["brand"]["play_store_url"],
            },
            "products": products,
        })

    return {
        "version": "1.0",
        "source_engine": data.get("engine"),
        "generated_at": data.get("generated_at"),
        "brand": config["brand"],
        "creative_defaults": config["creative_defaults"],
        "ads": ads,
    }


def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT

    config = load_json(CONFIG_PATH)
    data = load_json(input_path)

    manifest = build_manifest(data, config)
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 80)
    print("TRUSTFOLIO CREATIVE AD MANIFEST V1")
    print("=" * 80)
    print("Input :", input_path)
    print("Output:", output_path)
    print("Ads   :", len(manifest["ads"]))
    print("Brand :", manifest["brand"]["name"])
    print("Web   :", manifest["brand"]["website_url"])
    print("Play  :", manifest["brand"]["play_store_url"])
    print("=" * 80)


if __name__ == "__main__":
    main()
