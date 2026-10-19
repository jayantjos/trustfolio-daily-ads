"""Verify ranked product IDs and displayed prices survive every ads-only transform.

The source of truth is the existing TrustFolio site's Top-5 endpoint plus its
live-price overlay. This module does NOT query databases, choose products,
re-rank anything, or change TrustFolio website/backend code.
"""
from decimal import Decimal, InvalidOperation


ALLOWED_PRICE_SOURCES = frozenset(("website_live_price_api", "website_catalog"))


def _rupees(value, field):
    try:
        amount = Decimal(str(value))
    except (TypeError, InvalidOperation):
        raise ValueError(field + ": missing/invalid price") from None
    if not amount.is_finite() or amount <= 0 or amount != amount.to_integral_value():
        # Current approved image renderer prints whole rupees. Do not silently
        # round a fractional price that the website API actually returned.
        raise ValueError(field + ": cannot render a missing, fractional or invalid rupee price")
    return int(amount)


def _ranked_rows(products, label, id_field, price_field):
    if not isinstance(products, list) or len(products) != 5:
        raise ValueError(label + ": expected exactly five product rows")
    result = []
    for rank, item in enumerate(products, 1):
        if not isinstance(item, dict):
            raise ValueError(label + ": invalid product object at rank " + str(rank))
        if int(item.get("rank", rank)) != rank:
            raise ValueError(label + ": ranking reordered at " + str(rank))
        product_id = str(item.get(id_field) or "").strip()
        if not product_id:
            raise ValueError(label + ": missing product ID at rank " + str(rank))
        price = _rupees(item.get(price_field), label + " rank " + str(rank))
        result.append((product_id, price))
    if len({x[0] for x in result}) != 5:
        raise ValueError(label + ": duplicate product IDs")
    return result


def verify_ranked_price_pipeline(api_ad, linked_ad, creative_ad, infographic):
    """Require 5 identical (product_id, rounded-free rupee price) pairs in order.

    The exact five site-ranked products are never replaced/re-ranked; each
    visual podium uses the same per-rank price that the website overlay showed.
    """
    api_rows=_ranked_rows(api_ad.get("products"),"Top-5+live-price source","product_id","price_inr")
    linked_rows=_ranked_rows(linked_ad.get("products"),"ad-link manifest","product_id","price_inr")
    cards=(creative_ad.get("image_ad") or {}).get("products")
    creative_rows=_ranked_rows(cards,"creative image spec","source_product_id","price")
    visual_rows=_ranked_rows(infographic.get("products"),"infographic render payload","source_product_id","price_inr")
    expected=api_rows
    for stage,rows in (("ad-link manifest",linked_rows),
                       ("creative image spec",creative_rows),
                       ("infographic render payload",visual_rows)):
        if rows != expected:
            raise ValueError(stage + ": product ID / displayed price changed from live website source")
    sources=[p.get("price_source") for p in api_ad["products"]]
    if any(source not in ALLOWED_PRICE_SOURCES for source in sources):
        raise ValueError("Unverified product price source: live API/catalog provenance missing")
    if api_ad.get("live_price_refresh_completed") is not True:
        raise ValueError("Website live-price overlay not completed")
    return {
        "source_product_ids_by_rank":[p[0] for p in expected],
        "displayed_prices_by_rank":[p[1] for p in expected],
        "visual_prices_by_rank":[p[1] for p in visual_rows],
        "price_sources_by_rank":sources,
        "live_api_priced_products":sources.count("website_live_price_api"),
        "catalog_fallback_products":sources.count("website_catalog"),
    }
