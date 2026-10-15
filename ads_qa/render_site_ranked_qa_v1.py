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
from master_template_renderer_final_v5 import render as render_final

ADS = Path.home() / "new_scraper" / "ads"


def run(category, budget, brand, output_dir):
    input_payload = build_site_ads_payload(category, budget, brand)
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
    ranked_ids = [p.get("product_id") for p in ad["products"]]
    if any(not pid for pid in ranked_ids) or len(set(ranked_ids)) != 5:
        raise ValueError("Website ranked product IDs missing or duplicated")

    generated = visual_manifest(linked, visual_template)
    if len(generated["ads"]) != 1:
        raise ValueError("Creative generator failed to preserve site-ranked campaign")
    info = build_payload(generated["ads"][0])
    if info["site_ranking_status"] != "verified":
        raise ValueError("Infographic payload lost website ranking verification")
    visual_ids = [p.get("source_product_id") for p in info["products"]]
    if visual_ids != ranked_ids:
        raise ValueError("Product identity changed in infographic generation")

    # This renderer uses the existing approved backdrop and assigns product
    # position by rank 1=centre, 2=left, 3=right, 4/5=bottom.
    rendered = render_final(info)
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
        "landing_url": ad["landing_url"],
        "source_ad_id": ad["ad_id"],
        "source_product_ids_by_rank": ranked_ids,
        "visual_product_ids_by_rank": visual_ids,
        "source_observed_at": input_payload["generated_at"],
        "png": target.name,
        "dimensions": [1024,1536],
        "design_reference_status": "separate_visual_review_required",
        "automatic_publication": False
    }
    (output_dir/"website-top5-render-qa.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    print("TRUSTFOLIO_SITE_RENDER_SUCCESS")
    print("SITE_RANKING_VERIFIED=true")
    print("PRODUCT_ID_ORDER="+",".join(ranked_ids))
    print("RENDERED_IMAGE="+str(target))
    print("LANDING_URL="+ad["landing_url"])
    print("PUBLISH_STATUS=NOT_PUBLISHED_VISUAL_QA_REQUIRED")
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category",default="smartwatches")
    parser.add_argument("--budget",type=int,default=2000)
    parser.add_argument("--brand",default="")
    parser.add_argument("--output-dir",required=True)
    args = parser.parse_args()
    run(args.category,args.budget,args.brand,args.output_dir)


if __name__=="__main__":
    main()
