#!/usr/bin/env python3
"""Render one real website-ranked TrustFolio infographic for isolated server QA.

Reads only the public website API, config, and ad renderer assets.
Writes a report and PNG under the ads project, NEVER under ~/apps/trustfolio.
No publishing or automatic scheduling is performed.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

# Direct execution as ads_qa/script.py must still resolve the sibling ads
# modules; never import from or modify ~/apps/trustfolio.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image

from site_top5_ads_v1 import build_site_ads_payload
from ad_link_manifest_v1 import build_manifest as link_manifest
from creative_generator_v1 import build_manifest as visual_manifest
from build_infographic_payload_v1 import build_payload
from master_template_renderer_html_v4 import render as render_final
from ads_qa.price_rank_parity_v1 import verify_ranked_price_pipeline

ADS = Path.home() / "new_scraper" / "ads"


def run(category, budget, brand, output_dir, mode="budget"):
    if mode not in ("budget", "brand_budget", "comparison"):
        raise ValueError("Unknown advertisement mode")
    if mode == "brand_budget" and not brand:
        raise ValueError("A brand ad must use a verified brand")
    if mode != "brand_budget" and brand:
        raise ValueError("Only brand-budget campaigns may contain a brand filter")
    input_payload = build_site_ads_payload(category, budget, brand)
    if mode == "comparison":
        # Compare five DIFFERENT site-ranked products, never claim that one
        # product has matching retailer listings without identity evidence.
        from creative_generator_v1 import display_category
        input_payload["ads"][0]["ad_type"] = "top5_comparison"
        input_payload["ads"][0]["headline"] = (
            f"Compare Top 5 {display_category(category)} Under ₹{int(budget):,}"
        )
    # Avoid overwriting existing daily creative outputs during isolated QA.
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    input_payload["ads"][0]["model"] = "live-website-qa-" + timestamp
    config = json.loads((ADS / "creative_config_v1.json").read_text("utf8"))
    visual_template = json.loads((ADS / "creative_templates_v1.json").read_text("utf8"))
    linked = link_manifest(input_payload, config)
    if len(linked["ads"]) != 1:
        raise ValueError("Expected one campaign")
    ad = linked["ads"][0]
    if ad["site_ranking_status"] != "verified" or not ad["prefill_ready"]:
        raise ValueError("Website ranking or budget/brand deep-link is not verified")
    if len(ad["products"]) != 5:
        raise ValueError("Expected exactly five website-ranked products")
    if input_payload["ads"][0].get("live_price_refresh_completed") is not True:
        raise ValueError("Website live-price refresh was not run before rendering")
    ranked_ids = [p.get("product_id") for p in ad["products"]]
    if any(not pid for pid in ranked_ids) or len(set(ranked_ids)) != 5:
        raise ValueError("Website ranked product IDs missing or duplicated")

    generated = visual_manifest(linked, visual_template)
    if len(generated["ads"]) != 1:
        raise ValueError("Creative generator failed to preserve site-ranked campaign")
    info = build_payload(generated["ads"][0])
    # The website already performed the original Top-5 selection and the
    # website-matched live/catalog price overlay. Never change rank or price
    # while turning those values into the approved 3D ad visual.
    checked_prices = verify_ranked_price_pipeline(
        input_payload["ads"][0], ad, generated["ads"][0], info
    )
    if info["site_ranking_status"] != "verified":
        raise ValueError("Infographic payload lost website ranking verification")
    visual_ids = [p.get("source_product_id") for p in info["products"]]
    if visual_ids != ranked_ids:
        raise ValueError("Product identity changed in infographic generation")

    # This renderer uses the existing approved backdrop and assigns product
    # position by rank 1=centre, 2=left, 3=right, 4/5=bottom.
    rendered = render_final(info)
    geometry = json.loads(Path(rendered).with_suffix(".json").read_text("utf8"))
    with Image.open(rendered) as image:
        if image.size != (1024,1536):
            raise ValueError("Unexpected server ad dimensions")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True,exist_ok=True)
    target = output_dir / "trustfolio-live-website-top5-1024x1536.png"
    if Path(rendered).resolve() != target.resolve():
        import shutil
        shutil.copy2(rendered,target)
    report = {
        "source": "live_trustfolio_website_api",
        "website_api": "https://api.trustfolio.in/api/products/top",
        "website_match_status": "verified_at_generation",
        "campaign_category": category,
        "campaign_budget_inr": budget,
        "campaign_brand": brand or None,
        "campaign_mode": mode,
        "campaign_headline": input_payload["ads"][0].get("headline"),
        "landing_url": ad["landing_url"],
        "source_ad_id": ad["ad_id"],
        "source_product_ids_by_rank": ranked_ids,
        "visual_product_ids_by_rank": visual_ids,
        "live_price_refresh_completed": input_payload["ads"][0].get("live_price_refresh_completed") is True,
        "live_price_api": "https://api.trustfolio.in/api/live-prices",
        "price_sources_by_rank": [p.get("price_source") for p in ad["products"]],
        "live_statuses_by_rank": [p.get("live_price_status") for p in ad["products"]],
        "original_catalog_prices_by_rank": [p.get("stored_price_inr") for p in ad["products"]],
        "displayed_prices_by_rank": checked_prices["displayed_prices_by_rank"],
        "visual_prices_by_rank": checked_prices["visual_prices_by_rank"],
        "price_parity_verified": True,
        "live_api_priced_products": checked_prices["live_api_priced_products"],
        "catalog_fallback_products": checked_prices["catalog_fallback_products"],
        "source_observed_at": input_payload["generated_at"],
        "png": target.name,
        "dimensions": [1024,1536],
        "design_reference_status": "separate_visual_review_required",
        "visual_geometry_errors": geometry.get("errors") or [],
        "renderer": "master_template_renderer_html_v4",
        "automatic_publication": False
    }
    (output_dir/"website-top5-render-qa.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    print("TRUSTFOLIO_SITE_RENDER_SUCCESS")
    print("SITE_RANKING_VERIFIED=true")
    print("LIVE_PRICE_REFRESH_COMPLETED=true")
    print("DISPLAYED_PRICES=" + ",".join(str(p.get("price_inr")) for p in ad["products"]))
    print("PRICE_SOURCES=" + ",".join(str(p.get("price_source")) for p in ad["products"]))
    print("VISUAL_PRICE_RANK_PARITY_VERIFIED=true")
    print("LIVE_API_PRICES=" + str(checked_prices["live_api_priced_products"]))
    print("CATALOG_FALLBACK_PRICES=" + str(checked_prices["catalog_fallback_products"]))
    print("PRODUCT_ID_ORDER="+",".join(ranked_ids))
    print("RENDERED_IMAGE="+str(target))
    print("LANDING_URL="+ad["landing_url"])
    print("DESIGN_GEOMETRY_ERRORS=" + str(len(report["visual_geometry_errors"])))
    print("PUBLISH_STATUS=NOT_PUBLISHED_VISUAL_QA_REQUIRED")
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category",default="smartwatches")
    parser.add_argument("--budget",type=int,default=2000)
    parser.add_argument("--brand",default="")
    parser.add_argument("--mode",choices=("budget","brand_budget","comparison"),default="budget")
    parser.add_argument("--output-dir",required=True)
    args = parser.parse_args()
    run(args.category,args.budget,args.brand,args.output_dir,mode=args.mode)


if __name__=="__main__":
    main()
