"""Mirror TrustFolio's product-table live-price overlay before rendering an ad.

Source contract (verified on website VPS, 2026-10-18):
GET /api/products/top -> POST /api/live-prices with exactly the returned IDs.
Frontend ProductsTable: price=live.price_inr only when live.status='ok';
otherwise display stored price. Hide rows marked deleted; never advertise
out-of-stock products. Croma has no live Worker and uses catalog price.
"""
import json
from math import isfinite
from urllib.request import Request, urlopen

LIVE_PRICE_URL = "https://api.trustfolio.in/api/live-prices"
MAX_REPLY_BYTES = 300_000


def fetch_live_price_rows(product_ids, *, opener=urlopen):
    """Call the same price refresh endpoint as the TrustFolio results page."""
    ids = [str(v).strip() for v in product_ids]
    if len(ids) != 5 or any(not v for v in ids) or len(set(ids)) != 5:
        raise ValueError("Live price refresh requires five unique website product IDs")
    request = Request(
        LIVE_PRICE_URL,
        data=json.dumps({"ids": ids}).encode("utf8"),
        headers={"Accept": "application/json", "Content-Type": "application/json",
                 "User-Agent": "TrustFolioAdsWebsiteParity/1.1"},
        method="POST",
    )
    try:
        with opener(request, timeout=30) as reply:
            if reply.status != 200 or "json" not in reply.headers.get("Content-Type", "").lower():
                raise ValueError("Live price API did not return successful JSON")
            raw = reply.read(MAX_REPLY_BYTES + 1)
    except (TimeoutError, ConnectionError, OSError) as error:
        raise ValueError("Live price refresh unavailable; creative withheld") from error
    if len(raw) > MAX_REPLY_BYTES:
        raise ValueError("Live price API response too large")
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("Invalid JSON from live price API") from error
    if body.get("success") is not True or not isinstance(body.get("data"), list):
        raise ValueError("Live price API returned no valid price rows")
    return body["data"]


def overlay_site_live_prices(site_response, live_rows, budget_inr):
    """Use the same displayed price as ProductsTable, preserving five original ranks.

    Unlike the public page (which may display a refreshed price above its
    original search budget), an 'Under ₹X' advert must not claim such a price.
    Skip the creative instead of re-ranking or silently substituting products.
    """
    products = site_response.get("products") if isinstance(site_response, dict) else None
    if not isinstance(products, list) or len(products) != 5:
        raise ValueError("Website did not return five products")
    if not isinstance(live_rows, list):
        raise ValueError("Live price response missing")
    by_id = {}
    for row in live_rows:
        if not isinstance(row, dict) or not str(row.get("id") or "").strip():
            raise ValueError("Invalid live price row")
        key = str(row["id"])
        if key in by_id:
            raise ValueError("Duplicate live price product ID")
        by_id[key] = row
    requested_ids = [str(p.get("id") or "") for p in products]
    if set(by_id) != set(requested_ids) or len(by_id) != 5:
        raise ValueError("Live price response does not match the website Top-5 IDs")
    refreshed = []
    for product in products:
        product_id = str(product["id"])
        row = by_id[product_id]
        live = row.get("live")
        if row.get("deleted") is True or (isinstance(live, dict) and live.get("status") == "out_of_stock"):
            raise ValueError("Website removed an out-of-stock Top-5 item; ad withheld")
        copy = dict(product)
        copy["stored_price_inr"] = product.get("price_inr")
        copy["price_source"] = "website_catalog"
        copy["live_price_status"] = live.get("status") if isinstance(live, dict) else None
        copy["live_checked_at"] = live.get("checked_at") if isinstance(live, dict) else None
        copy["live_priced_at"] = live.get("priced_at") if isinstance(live, dict) else None
        # Exactly the same price display rule as the website ProductsTable.
        if isinstance(live, dict) and live.get("status") == "ok":
            try:
                amount = float(live["price_inr"])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("Live ok status has no valid price") from error
            if not isfinite(amount) or amount <= 0:
                raise ValueError("Live ok status has invalid price")
            copy["price_inr"] = amount
            copy["price_source"] = "website_live_price_api"
        try:
            price = float(copy["price_inr"])
        except (TypeError, ValueError, KeyError) as error:
            raise ValueError("Top-5 product has no usable price") from error
        if not isfinite(price) or not (0 < price <= budget_inr):
            raise ValueError("Displayed price exceeds advertised budget; ad withheld")
        refreshed.append(copy)
    result = dict(site_response)
    result["products"] = refreshed
    return result
