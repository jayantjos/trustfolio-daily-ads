#!/usr/bin/env python3
"""TrustFolio dynamic master-template renderer entrypoint.

This wrapper keeps the existing Pillow reference renderer as the drawing engine,
but validates the daily payload and guarantees category/title/prices/products
are data-driven. It intentionally renders one requested ad for QA; batch publishing
is a separate, explicit step.
"""
import json
import re
import sys
from pathlib import Path

BASE = Path.home() / "new_scraper"
ADS_DIR = BASE / "ads"
DEFAULT_INPUT = ADS_DIR / "trustfolio_infographic_payload_v1.json"
sys.path.insert(0, str(ADS_DIR))

import creative_renderer_v6 as drawing_engine


def money(value):
    if value in (None, ""):
        return None
    try:
        return f"₹{float(value):,.0f}"
    except (TypeError, ValueError):
        return None


def validate_ad(ad):
    metadata = ad.get("metadata") or {}
    title = str(metadata.get("campaign_title") or "").strip()
    category = str(metadata.get("campaign_category") or "").strip()
    products = ad.get("products") or []
    if not title:
        raise ValueError("Missing campaign_title; refusing to invent a headline.")
    if not category:
        raise ValueError("Missing campaign_category.")
    if len(products) < 5:
        raise ValueError(f"Expected 5 source products, got {len(products)}.")
    if "budget" in title.lower() and not re.search(r"₹\s*[\d,]+", title):
        raise ValueError("Budget ad headline has no source-backed rupee amount.")
    for i, p in enumerate(products[:5], 1):
        if p.get("price_inr") in (None, ""):
            raise ValueError(f"Product #{i} has no price; refusing to render an invented price.")
        if not (p.get("image_url") or "").strip():
            print(f"WARNING: product #{i} has no image URL; renderer may show an empty image slot.")
    return title, category, products[:5]


def adapt_ad(payload_ad):
    title, category, products = validate_ad(payload_ad)
    adapted_products = []
    for p in products:
        specs = p.get("key_specs") or []
        if isinstance(specs, dict):
            specs = [f"{k}: {v}" for k, v in specs.items()]
        adapted_products.append({
            "image_url": p.get("image_url") or "",
            "full_title": str(p.get("name") or "").strip(),
            "title": str(p.get("name") or "").strip(),
            "price": p.get("price_inr"),
            "price_display": money(p.get("price_inr")) or "",
            "platform": str(p.get("retailer") or "").strip(),
            "rating": p.get("verified_rating"),
            "specifications": {f"Feature {i+1}": str(s) for i, s in enumerate(specs[:3])},
        })
    return {
        "ad_id": payload_ad.get("source_ad_id") or "unknown",
        "ad_type": payload_ad.get("source_ad_type") or "budget_recommendation",
        "category": category.lower().replace(" ", "-"),
        "headline": title,
        "image_ad": {"products": adapted_products},
        "landing_url": payload_ad.get("landing_url") or "",
    }


def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    ad_id = sys.argv[2] if len(sys.argv) > 2 else ""
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    ads = payload.get("ads") or []
    if not ads:
        raise SystemExit("No ads found in payload.")
    selected = next((a for a in ads if a.get("source_ad_id") == ad_id), None) if ad_id else ads[0]
    if selected is None:
        raise SystemExit(f"Ad ID not found: {ad_id}")
    adapted = adapt_ad(selected)
    drawing_engine.OUT_DIR = ADS_DIR / "generated_creatives" / "feed"
    drawing_engine.VERSION = "MASTER_V1"
    drawing_engine.render(adapted)
    output = drawing_engine.OUT_DIR / f"{adapted['ad_id']}_premium_1080x1350.png"
    print("=" * 80)
    print("TRUSTFOLIO MASTER TEMPLATE RENDERER V1")
    print("AD ID   :", adapted["ad_id"])
    print("CATEGORY:", adapted["category"])
    print("HEADLINE:", adapted["headline"])
    print("PRODUCTS:", len(adapted["image_ad"]["products"]))
    print("OUTPUT  :", output)
    print("NOTE    : Rendered for QA; inspect before batch publishing.")
    print("=" * 80)


if __name__ == "__main__":
    main()
