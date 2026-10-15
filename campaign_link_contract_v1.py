"""Fail-closed TrustFolio campaign URL + site-ranking contracts.

The ad pipeline must not assume that the web frontend supports query prefills
or that an independently selected ad Top 5 equals the website's Top 5.
"""
import re
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl


def requested_filters(ad):
    category = str(ad.get("category") or "").strip()
    brand = str(ad.get("brand") or "").strip()
    raw_budget = ad.get("budget_inr")
    try:
        budget = int(float(raw_budget)) if raw_budget not in (None, "") else None
    except (TypeError, ValueError):
        raise ValueError("Invalid campaign budget")
    if budget is not None and budget <= 0:
        raise ValueError("Campaign budget must be positive")
    return {"category": category, "budget_inr": budget, "brand": brand}


def _verified_option(option):
    # Explicit BOTH flags are needed. Never turn on a filter solely on the basis
    # of a query parameter name; the frontend must parse and apply that field.
    return bool(option.get("enabled") is True and option.get("frontend_verified") is True)


def campaign_link(ad, config, ad_id):
    filters = requested_filters(ad)
    slug = config["links"].get("route_slug_overrides", {}).get(
        filters["category"], filters["category"]
    )
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(slug)):
        raise ValueError("Unrecognized category route slug: " + str(slug))
    base = config["links"]["category_url_template"].format(route_slug=slug)
    parsed = urlsplit(base)
    if parsed.scheme != "https" or parsed.hostname not in ("trustfolio.in", "www.trustfolio.in"):
        raise ValueError("Category landing URL must be on HTTPS TrustFolio")
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    tracking = config["links"].get("tracking", {}).get("parameters", {})
    params.update(tracking)
    params["utm_content"] = ad_id
    params["ad_type"] = str(ad.get("ad_type") or "")
    ready = {}
    for key, requested in (("budget", filters["budget_inr"]), ("brand", filters["brand"])):
        if requested in (None, ""):
            continue
        cfg = config["links"].get(
            "budget_query_parameter" if key == "budget" else "brand_query_parameter", {}
        )
        is_ready = _verified_option(cfg)
        ready[key] = is_ready
        if is_ready:
            name = str(cfg.get("parameter") or key)
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
                raise ValueError("Invalid verified query parameter")
            params[name] = str(requested)
    url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(params), parsed.fragment))
    return {
        "landing_url": url,
        "requested_filters": filters,
        "prefill_ready": bool(all(ready.values())),
        "verified_prefill_fields": [key for key, valid in ready.items() if valid],
        "unverified_prefill_fields": [key for key, valid in ready.items() if not valid],
        # Ranking comes from the ad engine until an actual site snapshot confirms
        # that the same product IDs are displayed in the same order.
        "site_ranking_status": "unverified",
        "click_destination": "category_landing",
    }


def check_ranked_site_snapshot(ad, snapshot):
    """Validate an ad against a real website/API Top-5 response, NOT a guessed list.

    Both inputs must describe the same category/brand/budget query.
    An absent or incomplete snapshot is a failure, not an assumed match.
    """
    problems = []
    expected = requested_filters(ad)
    if not isinstance(snapshot, dict):
        return ["website ranking snapshot missing"]
    observed = requested_filters(snapshot)
    if expected != observed:
        problems.append("website category, budget or brand filters differ")
    products = ad.get("products") or []
    if not isinstance(products, list):
        return problems + ["ad products must be a ranked list"]
    website_products = snapshot.get("products") or []
    if not isinstance(website_products, list):
        return problems + ["website products must be a ranked list"]
    if len(products) != 5 or len(website_products) != 5:
        problems.append("both ad and website must contain five products")
    for i, (left, right) in enumerate(zip(products, website_products), start=1):
        if not isinstance(left, dict) or not isinstance(right, dict):
            problems.append("product row is not an object")
            continue
        ad_rank = int(left.get("rank") or i)
        web_rank = int(right.get("rank") or i)
        if ad_rank != i or web_rank != i:
            problems.append(f"rank sequence differs at slot {i}")
        ad_id = str(left.get("product_id") or left.get("source_product_id") or "").strip()
        web_id = str(right.get("product_id") or right.get("id") or "").strip()
        if not ad_id or not web_id:
            problems.append(f"missing source product ID at rank {i}")
        elif ad_id != web_id:
            problems.append(f"website product ID mismatch at rank {i}")
        raw_price = left.get("price_inr", left.get("price"))
        if raw_price not in (None, "") and expected["budget_inr"] is not None:
            try:
                if float(raw_price) > expected["budget_inr"]:
                    problems.append(f"ad product exceeds advertised budget at rank {i}")
            except (TypeError, ValueError):
                problems.append(f"invalid price at rank {i}")
        if expected["brand"]:
            name = str(left.get("brand") or "").strip().casefold()
            if name != expected["brand"].casefold():
                problems.append(f"ad product brand mismatch at rank {i}")
    return problems
