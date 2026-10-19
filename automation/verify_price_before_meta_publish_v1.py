"""Fail-closed Meta prepublication check against fresh TrustFolio website prices.

The approved image was rendered from GET /api/products/top and a second
POST /api/live-prices. Re-run those EXACT website-backed requests immediately
before an automated Facebook/Instagram publication; if a price or ranking
changed, do not publish the now-stale static poster.

A successful live-price refresh does NOT mean all five prices are
independently live. The backend may return catalog-price fallback, which
is counted separately and never misreported as a live-verified product.
"""
import argparse
from datetime import datetime, timezone
import json
from math import isfinite
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from site_top5_ads_v1 import build_site_ads_payload


class PriceAuditBlocked(ValueError):
    """The ad price/ranking snapshot must not be published."""


SOURCES = {"website_live_price_api", "website_catalog"}


def _price(value, budget, *, label):
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise PriceAuditBlocked(label + " is not numeric") from None
    if not isfinite(amount) or not (0 < amount <= budget):
        raise PriceAuditBlocked(label + " is invalid or exceeds the advertised budget")
    return amount


def verify_fresh_snapshot(plan, report, *, fetcher=build_site_ads_payload,
                          now=None, max_age_seconds=1200):
    """Return audit metadata only when poster prices still match both APIs."""
    if plan.get("status") != "eligible":
        raise PriceAuditBlocked("Cannot publish campaign with no five website products")
    if report.get("source") != "live_trustfolio_website_api":
        raise PriceAuditBlocked("Unverified ranking source")
    if report.get("live_price_refresh_completed") is not True:
        raise PriceAuditBlocked("Image did not complete its pre-render live-price check")
    if report.get("campaign_category") != plan.get("category"):
        raise PriceAuditBlocked("Rendered category does not match selected campaign")
    if report.get("campaign_brand") not in (plan.get("brand") or "", None):
        raise PriceAuditBlocked("Rendered brand does not match selected campaign")
    if report.get("campaign_mode") != plan.get("mode"):
        raise PriceAuditBlocked("Rendered ad mode does not match selected campaign")
    try:
        budget=int(plan["budget"])
        if int(report["campaign_budget_inr"]) != budget:
            raise PriceAuditBlocked("Poster budget does not match selected budget")
    except (TypeError, KeyError, ValueError):
        raise PriceAuditBlocked("Invalid image price budget") from None

    ids=report.get("visual_product_ids_by_rank")
    source_ids=report.get("source_product_ids_by_rank")
    prices=report.get("displayed_prices_by_rank")
    sources=report.get("price_sources_by_rank")
    statuses=report.get("live_statuses_by_rank")
    if (not isinstance(ids,list) or len(ids)!=5 or
        ids!=source_ids or len(set(ids))!=5 or not all(ids)):
        raise PriceAuditBlocked("Image's website Top-5 product IDs are invalid")
    if any(not isinstance(arr,list) or len(arr)!=5 for arr in (prices,sources,statuses)):
        raise PriceAuditBlocked("Image has no complete price provenance audit")
    validated_prices=[_price(v,budget,label="Rendered price") for v in prices]
    for idx,(source,status) in enumerate(zip(sources,statuses)):
        if source not in SOURCES:
            raise PriceAuditBlocked("Image has unknown price source for rank "+str(idx+1))
        if source=="website_live_price_api" and status!="ok":
            raise PriceAuditBlocked("Image claims live price without an OK price response")

    try:
        observed=datetime.fromisoformat(str(report["source_observed_at"]).replace("Z","+00:00"))
    except (KeyError,TypeError,ValueError):
        raise PriceAuditBlocked("Missing valid image generation timestamp") from None
    if observed.tzinfo is None:
        raise PriceAuditBlocked("Image generation timestamp requires timezone")
    current=now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise PriceAuditBlocked("Current time requires timezone")
    age=(current-observed).total_seconds()
    if not (-60 <= age <= max_age_seconds):
        raise PriceAuditBlocked("Image price snapshot is too old to publish; regenerate")

    # The GET includes refreshed website ranking and budget; the POST refreshes
    # exactly five IDs. This fails closed if either API fails or loses product identity.
    payload=fetcher(plan["category"],budget,plan.get("brand") or "")
    if not isinstance(payload,dict) or not isinstance(payload.get("ads"),list) or len(payload["ads"])!=1:
        raise PriceAuditBlocked("Live website returned no verified product payload")
    latest=payload["ads"][0]
    if latest.get("ranking_source")!="live_trustfolio_website_api":
        raise PriceAuditBlocked("Latest website ranking was not verified")
    if latest.get("live_price_refresh_completed") is not True:
        raise PriceAuditBlocked("Latest website live-price API refresh did not complete")
    products=latest.get("products")
    if not isinstance(products,list) or len(products)!=5:
        raise PriceAuditBlocked("Website no longer has five verified products")
    recent_ids=[str(p.get("product_id") or "") for p in products]
    if recent_ids!=ids:
        raise PriceAuditBlocked("Website product ranking changed after poster was rendered")
    for rank,product in enumerate(products):
        recent_price=_price(product.get("price_inr"),budget,label="Latest price")
        if abs(recent_price-validated_prices[rank])>0.009:
            raise PriceAuditBlocked("Website latest price changed for rank "+str(rank+1))
        recent_source=product.get("price_source")
        if recent_source!=sources[rank]:
            raise PriceAuditBlocked("Website live/catalog price provenance changed at rank "+str(rank+1))
        if recent_source=="website_live_price_api" and product.get("live_price_status")!="ok":
            raise PriceAuditBlocked("Website live price status changed at rank "+str(rank+1))

    return {
        "verified_at":current.isoformat(),
        "category":plan["category"],
        "budget_inr":budget,
        "five_ranked_products":len(ids),
        "live_prices":sum(x=="website_live_price_api" for x in sources),
        "catalog_fallback_prices":sum(x=="website_catalog" for x in sources),
        "source_age_seconds":round(age,1),
        "comparison":"same_website_rank_product_ids_and_display_prices",
        "publication_approved":True,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--plan",required=True)
    parser.add_argument("--report",required=True)
    args=parser.parse_args()
    plan=json.loads(Path(args.plan).read_text("utf8"))
    report=json.loads(Path(args.report).read_text("utf8"))
    audit=verify_fresh_snapshot(plan,report)
    print("META_PREPUBLISH_PRICE_PARITY=PASS")
    print("VERIFIED_WEBSITE_RANKED_PRODUCTS="+str(audit["five_ranked_products"]))
    print("VERIFIED_LIVE_PRICE_COUNT="+str(audit["live_prices"]))
    print("CATALOG_FALLBACK_PRICE_COUNT="+str(audit["catalog_fallback_prices"]))
    print("IMAGE_PRICE_SNAPSHOT_AGE_SECONDS="+str(audit["source_age_seconds"]))
    print("LIVE_PRICING_COMPLETE_DOES_NOT_MEAN_ALL_FIVE_LIVE=true")


if __name__=="__main__":
    main()
