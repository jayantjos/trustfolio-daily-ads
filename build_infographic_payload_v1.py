#!/usr/bin/env python3
"""
Build the approved TrustFolio infographic payload from the daily creative
manifest. The master visual contract is defined in trustfolio_infographic_data_v1.py;
daily product values come from the generated ad manifest.

The renderer should never invent product prices, merchants, specs, or images.
"""

import json
import sys
from pathlib import Path

BASE = Path.home() / "new_scraper"
INPUT = BASE / "ads" / "creative_generation_manifest_v1.json"
OUTPUT = BASE / "ads" / "trustfolio_infographic_payload_v1.json"

MASTER_PATH = BASE / "ads" / "trustfolio_infographic_data_v1.py"
sys.path.insert(0, str(MASTER_PATH.parent))

from ads_qa.category_copy_v1 import category_tagline

from trustfolio_infographic_data_v1 import (
    cta_button,
    feature_badges,
    infographic_metadata,
    trust_highlights,
)

CATEGORY_NAMES = {
    "smart-phones": "Smartphones",
    "smart-tvs": "Smart TVs",
    "air-conditioners": "Air Conditioners",
    "air-coolers": "Air Coolers",
    "ceiling-fans": "Ceiling Fans",
    "water-purifiers": "Water Purifiers",
    "mixer-grinders": "Mixer Grinders",
    "headphones-earbuds": "Headphones & Earbuds",
    "desktop-computers": "Desktop Computers",
    "vacuum-cleaners": "Vacuum Cleaners",
    "washing-machines": "Washing Machines",
    "microwave-ovens": "Microwave Ovens",
    "induction-cooktops": "Induction Cooktops",
}


def category_label(value):
    return CATEGORY_NAMES.get(
        value,
        str(value or "").replace("-", " ").title(),
    )


def product_payload(product, rank):
    return {
        "rank": rank,
        "source_product_id": product.get("source_product_id") or "",
        "click_url": product.get("click_url") or "",
        "badge": "Best Value" if rank == 1 else None,
        "name": product.get("full_title") or product.get("title") or "",
        "tagline": "",
        "price_inr": product.get("price"),
        "retailer": product.get("platform") or "",
        "image_url": product.get("image_url") or "",
        "key_specs": [],
        "visual_position": {
            1: "Center podium (Largest display/prominence)",
            2: "Left podium",
            3: "Right podium",
            4: "Bottom Left",
            5: "Bottom Right",
        }.get(rank, ""),
        "verified_rating": product.get("rating"),
        "raw_specifications": product.get("specifications") or {},
    }


def build_payload(ad):
    category = ad.get("category") or ""
    products = (ad.get("image_ad") or {}).get("products") or []
    products = products[:5]

    title = ad.get("headline") or infographic_metadata["main_title"]

    metadata = dict(infographic_metadata)
    metadata["campaign_title"] = title
    metadata["campaign_category"] = category_label(category)

    # Data is dynamic, but copy MUST be category-specific. The original
    # smartwatch-only metadata subtitle must never leak into other ads.
    metadata["subtitle"] = category_tagline(
        category, ad_type=ad.get("ad_type") or ""
    )

    return {
        "metadata": metadata,
        "design_elements": {
            "background_theme": "Modern Premium Tech Showcase",
            "color_palette": {
                "primary": infographic_metadata["primary_colors"][:1] + ["Electric Blue", "Dark Navy Blue"],
                "highlights": ["Bright Yellow", "Gold"],
                "text": ["White", "Dark Blue", "Black"],
                "accents": ["Purple"],
            },
            "layout_features": {
                "podium_count": 3,
                "podium_color": "3D Blue",
                "has_top_crown_icon": True,
                "has_cta_search_bar": True,
                "cta_text": cta_button["text"],
            },
        },
        "key_usps": feature_badges,
        "trust_highlights": trust_highlights,
        "cta_button": cta_button,
        "products": [
            product_payload(product, i)
            for i, product in enumerate(products, start=1)
        ],
        "source_ad_id": ad.get("ad_id"),
        "source_ad_type": ad.get("ad_type"),
        "landing_url": ad.get("landing_url"),
        "site_ranking_status": ad.get("site_ranking_status") or "unverified",
        "prefill_ready": bool(ad.get("prefill_ready")),
        "ranking_source": ad.get("ranking_source"),
    }


def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else INPUT
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT

    data = json.loads(input_path.read_text(encoding="utf-8"))
    ads = data.get("ads") or []
    if not ads:
        raise SystemExit("No ads found in creative generation manifest.")

    payload = {
        "version": "1.0",
        "template": "TrustFolio approved reference infographic",
        "ads": [build_payload(ad) for ad in ads],
    }

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 88)
    print("TRUSTFOLIO INFOGRAPHIC PAYLOAD BUILDER V1")
    print("=" * 88)
    print("Ads     :", len(ads))
    print("Output  :", output_path)
    print("Template: TrustFolio approved reference infographic")
    print("=" * 88)


if __name__ == "__main__":
    main()
