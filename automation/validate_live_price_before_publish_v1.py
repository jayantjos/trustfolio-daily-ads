"""Fail closed if posted TrustFolio ad contains prices no longer shown by the live website.

Re-fetch the SAME ranked Top Five and POST their IDs to the website
/api/live-prices immediately before publishing via official Meta.
A displayed-price, source, ID, brand or rank change invalidates the immutable
JPEG. The image is NOT silently updated, substituted or published.
"""
import argparse
from datetime import datetime, timezone
import json
from math import isfinite
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from site_top5_ads_v1 import build_site_ads_payload
from website_live_price_sync_v1 import LIVE_PRICE_URL

PRICE_SOURCES=("website_live_price_api","website_catalog")


def verify_snapshot(plan, report, *, fetcher=build_site_ads_payload):
    if plan.get("status")!="eligible" or plan.get("mode") not in ("budget","brand_budget","comparison"):
        raise ValueError("Only eligible website-ranked campaigns may be published")
    if report.get("live_price_refresh_completed") is not True:
        raise ValueError("Rendered creative has no verified website live-price refresh")
    if report.get("live_price_api")!=LIVE_PRICE_URL:
        raise ValueError("Rendered live price source is not the verified website API")
    if report.get("source")!="live_trustfolio_website_api":
        raise ValueError("Rendered rankings do not come from the TrustFolio website")
    if (report.get("campaign_category")!=plan.get("category") or
            int(report.get("campaign_budget_inr") or 0)!=int(plan.get("budget") or 0) or
            (report.get("campaign_brand") or "")!=(plan.get("brand") or "") or
            report.get("campaign_mode")!=plan.get("mode")):
        raise ValueError("Rendered campaign category, budget, brand or ad type differs from plan")
    original_ids=report.get("source_product_ids_by_rank")
    original_prices=report.get("displayed_prices_by_rank")
    original_sources=report.get("price_sources_by_rank")
    if (not isinstance(original_ids,list) or len(original_ids)!=5 or
            len(set(original_ids))!=5 or
            not isinstance(original_prices,list) or len(original_prices)!=5 or
            not isinstance(original_sources,list) or len(original_sources)!=5 or
            any(x not in PRICE_SOURCES for x in original_sources)):
        raise ValueError("Missing five original ranked price observations")
    if original_ids != report.get("visual_product_ids_by_rank"):
        raise ValueError("Visual rankings do not match website IDs")
    if any(not isfinite(float(x)) or float(x)<=0 for x in original_prices):
        raise ValueError("Invalid displayed price in rendered ad")
    # The fetcher does TWO real API requests: Top Five, then live-prices POST.
    # Both are required by build_site_ads_payload, and any API failure aborts.
    current=fetcher(plan["category"],int(plan["budget"]),plan.get("brand") or "")
    ad=current["ads"][0]
    if ad.get("ranking_source")!="live_trustfolio_website_api" or ad.get("live_price_refresh_completed") is not True:
        raise ValueError("Current website live-price refresh was not completed")
    products=ad.get("products") or []
    if len(products)!=5:
        raise ValueError("Current website does not return exactly five products")
    current_ids=[p.get("product_id") for p in products]
    if current_ids!=original_ids:
        raise ValueError("Live website Top Five rank/product IDs changed after image rendering")
    current_prices=[float(p.get("price_inr")) for p in products]
    current_sources=[p.get("price_source") for p in products]
    if current_sources!=original_sources:
        raise ValueError("Displayed price source changed after image rendering")
    for before,after in zip(original_prices,current_prices):
        if not isfinite(after) or abs(float(before)-after)>0.009:
            raise ValueError("Live displayed product price changed after ad rendering; do not post stale JPG")
    for p in products:
        if (plan.get("brand") and p.get("brand","").casefold()!=str(plan["brand"]).casefold()):
            raise ValueError("Changed live brand invalidates the rendered ad")
        if float(p["price_inr"])>int(plan["budget"]):
            raise ValueError("Current website price exceeds advertised budget")
    return {
        "status":"verified_same_displayed_prices_before_publish",
        "campaign_id":plan.get("campaign_id"),
        "ranked_product_count":5,
        "website_live_price_api_refresh_attempted":True,
        "live_price_api_count":current_sources.count("website_live_price_api"),
        "website_catalog_fallback_count":current_sources.count("website_catalog"),
        "validated_at_utc":datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser=argparse.ArgumentParser(description="Check freshly displayed prices against immutable ranked ad JPG")
    parser.add_argument("--plan",required=True)
    parser.add_argument("--report",required=True)
    args=parser.parse_args()
    plan=json.loads(Path(args.plan).read_text("utf8"))
    report=json.loads(Path(args.report).read_text("utf8"))
    verified=verify_snapshot(plan,report)
    print("SITE_PRICE_AT_PUBLISH_GUARD=PASS")
    print("CAMPAIGN_ID="+str(verified["campaign_id"]))
    print("PRODUCTS_RECHECKED=5")
    print("LIVE_PRICE_API_USED_COUNT="+str(verified["live_price_api_count"]))
    print("WEBSITE_CATALOG_FALLBACK_COUNT="+str(verified["website_catalog_fallback_count"]))
    print("CHECKED_AT_UTC="+verified["validated_at_utc"])


if __name__=="__main__":
    main()
