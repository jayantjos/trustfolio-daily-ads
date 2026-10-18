#!/usr/bin/env python3
"""Build an ad payload from TrustFolio's own public Top-5 website API.

No access to the website source tree, database, or VPS app deployment is needed.
Ranks and product IDs come exclusively from the same live API used by the
website's /category/{slug}/products page, not a second MongoDB ranker.

Fails closed on short/missing lists, missing images, brand fallbacks, or invalid
pricing; this is intentionally stricter than the public site's UI.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from campaign_link_contract_v1 import campaign_link, check_ranked_site_snapshot
from website_live_price_sync_v1 import fetch_live_price_rows, overlay_site_live_prices

API_ORIGIN = "https://api.trustfolio.in"
MAX_RESPONSE_BYTES = 500_000
MAX_BUDGET_INR = 10_000_000


def _positive_budget(value):
    try:
        raw = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Budget must be numeric") from exc
    if not (0 < raw <= MAX_BUDGET_INR) or int(raw) != raw:
        raise ValueError("Budget must be a positive whole-rupee amount")
    return int(raw)


def _safe_category(value):
    slug = str(value or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("Invalid canonical website category slug")
    return slug


def _image_url(value):
    candidates = []
    if isinstance(value, str):
        candidates.append(value)
    elif isinstance(value, dict):
        candidates.extend(value.get(k) for k in ("url", "src", "image_url", "large") if isinstance(value.get(k), str))
    elif isinstance(value, list):
        for item in value[:8]:
            if isinstance(item, str):
                candidates.append(item)
            elif isinstance(item, dict):
                candidates.extend(item.get(k) for k in ("url", "src", "image_url") if isinstance(item.get(k), str))
    for candidate in candidates:
        parsed = urlsplit(candidate.strip())
        if parsed.scheme == "https" and parsed.hostname:
            return candidate.strip()
    return ""


def site_api_url(category, budget_inr, brand=""):
    category = _safe_category(category)
    budget_inr = _positive_budget(budget_inr)
    brand = str(brand or "").strip()
    if len(brand) > 100 or any(c in brand for c in "\r\n\x00"):
        raise ValueError("Invalid brand name")
    query = {"category": category, "budget": str(budget_inr), "limit": "5"}
    if brand:
        query["brand"] = brand
    return API_ORIGIN + "/api/products/top?" + urlencode(query)


def fetch_public_top5(category, budget_inr, brand="", *, opener=urlopen):
    """GET only; no credentials, writes, or source changes."""
    url = site_api_url(category, budget_inr, brand)
    request = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "TrustFolioAdsWebsiteParity/1.0",
    })
    with opener(request, timeout=20) as reply:
        if reply.status != 200 or "json" not in reply.headers.get("Content-Type", "").lower():
            raise ValueError("Website Top-5 API did not return a successful JSON response")
        data = reply.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("Website Top-5 API response exceeds size limit")
    payload = json.loads(data)
    if payload.get("success") is not True or not isinstance(payload.get("data"), dict):
        raise ValueError("Website Top-5 API response is unsuccessful")
    return payload["data"]


def normalize_site_ad(category, budget_inr, brand, response, *, generated_at=None):
    category = _safe_category(category)
    budget_inr = _positive_budget(budget_inr)
    brand = str(brand or "").strip()
    products = response.get("products") if isinstance(response, dict) else None
    if not isinstance(products, list) or len(products) != 5:
        raise ValueError("Website does not currently have exactly five ranked products")
    if brand and (response.get("partialBrandFill") or response.get("fallbackApplied")):
        raise ValueError("Website returned brand-fallback products; cannot claim a brand-only ad")

    normalized = []
    snapshot = []
    seen = set()
    for rank, original in enumerate(products, start=1):
        if not isinstance(original, dict):
            raise ValueError("Website product row must be an object")
        returned_rank = original.get("rank", rank)
        if int(returned_rank) != rank:
            raise ValueError("Website Top-5 rank order is inconsistent")
        product_id = str(original.get("id") or "").strip()
        title = str(original.get("title") or "").strip()
        product_brand = str(original.get("brand") or "").strip()
        platform = str(original.get("platform") or "").strip()
        if not product_id or product_id in seen or not title:
            raise ValueError("Duplicate/missing product ID or title in website Top 5")
        seen.add(product_id)
        try:
            price = float(original["price_inr"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Website Top-5 product has no valid price") from exc
        if not (0 < price <= budget_inr):
            raise ValueError("Website Top-5 price exceeds budget or is invalid")
        if brand and product_brand.casefold() != brand.casefold():
            raise ValueError("Website returned a different brand; brand ad withheld")
        image = _image_url(original.get("main_image")) or _image_url(original.get("images"))
        if not image:
            raise ValueError("Website Top-5 product is missing a verified HTTPS image URL")
        specs = original.get("specifications")
        normalized.append({
            "rank": rank,
            "product_id": product_id,
            "source_product_id": product_id,
            "title": title,
            "brand": product_brand,
            "price_inr": price,
            "stored_price_inr": original.get("stored_price_inr", original.get("price_inr")),
            "price_source": original.get("price_source") or "website_catalog",
            "live_price_status": original.get("live_price_status"),
            "live_checked_at": original.get("live_checked_at"),
            "live_priced_at": original.get("live_priced_at"),
            "image_url": image,
            "platform": platform,
            "rating": original.get("average_rating"),
            "specifications": specs if isinstance(specs, dict) else {},
            "category": category,
            "site_product_url": original.get("product_url") or None,
        })
        snapshot.append({"rank": rank, "product_id": product_id, "price_inr": price, "brand": product_brand})

    display = {
        "smart-phones": "Smartphones",
        "headphones-earbuds": "Headphones & Earbuds",
        "smart-tvs": "Smart TVs",
    }.get(category, category.replace("-", " ").title())
    label = ("Best " + brand + " " if brand else "Best ") + display + f" Under ₹{budget_inr:,}"
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    snapshot_record = {
        "category": category,
        "budget_inr": budget_inr,
        "brand": brand,
        "products": snapshot,
    }
    ad = {
        "ad_type": "brand_recommendation" if brand else "budget_recommendation",
        "category": category,
        "brand": brand,
        "budget_inr": budget_inr,
        "headline": label,
        "products": normalized,
        "ranking_source": "live_trustfolio_website_api",
        "website_snapshot": snapshot_record,
        "ranking_observed_at": generated_at,
        "website_match_type": response.get("matchType"),
        "website_fallback_applied": bool(response.get("fallbackApplied")),
    }
    problems = check_ranked_site_snapshot(ad, snapshot_record)
    if problems:
        raise ValueError("Website/ad ranking mismatch: " + "; ".join(problems))
    return ad


def build_site_ads_payload(category, budget_inr, brand="", *, opener=urlopen):
    response = fetch_public_top5(category, budget_inr, brand, opener=opener)
    source_products = response.get("products") if isinstance(response, dict) else None
    if not isinstance(source_products, list) or len(source_products) != 5:
        raise ValueError("Website does not currently have exactly five ranked products")
    ids = [str(p.get("id") or "") for p in source_products if isinstance(p, dict)]
    # Website results page makes this second request AFTER it fetches the Top-5.
    live_rows = fetch_live_price_rows(ids, opener=opener)
    refreshed = overlay_site_live_prices(response, live_rows, _positive_budget(budget_inr))
    ad = normalize_site_ad(category, budget_inr, brand, refreshed)
    ad["price_refresh_source"] = "trustfolio_website_live_prices_api"
    ad["live_price_refresh_completed"] = True
    return {
        "engine": "TrustFolio Website Top-5 + Live Price API",
        "generated_at": ad["ranking_observed_at"],
        "ranking_source": "live_trustfolio_website_api",
        "price_refresh_source": "trustfolio_website_live_prices_api",
        "ads": [ad],
    }


def main():
    parser = argparse.ArgumentParser(description="Read actual TrustFolio website Top 5 for one campaign")
    parser.add_argument("--category", required=True)
    parser.add_argument("--budget", required=True, type=int)
    parser.add_argument("--brand", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = build_site_ads_payload(args.category, args.budget, args.brand)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SITE_API_TOP5_MATCHED=5")
    print("CAMPAIGN_CATEGORY=" + _safe_category(args.category))
    print("CAMPAIGN_BUDGET=" + str(_positive_budget(args.budget)))
    print("SNAPSHOT_PATH=" + str(target))
    print("AUTOMATIC_SOCIAL_PUBLICATION=DISABLED")


if __name__ == "__main__":
    main()
