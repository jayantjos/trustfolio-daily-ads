#!/usr/bin/env python3
import json
import sys
import textwrap
from pathlib import Path
from urllib.parse import urlparse

BASE = Path.home() / "new_scraper"
DEFAULT_INPUT = BASE / "ads" / "creative_ad_manifest_v1.json"
DEFAULT_OUTPUT = BASE / "ads" / "creative_generation_manifest_v1.json"
TEMPLATE_PATH = BASE / "ads" / "creative_templates_v1.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def display_category(category: str) -> str:
    special = {
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
        "smartwatches": "Smartwatches",
    }
    return special.get(category, category.replace("-", " ").title())


def clean_product_name(title: str, max_chars: int = 58) -> str:
    title = " ".join(str(title or "").split())
    if len(title) <= max_chars:
        return title
    return title[: max_chars - 1].rstrip() + "…"


def format_inr(value):
    if value in (None, ""):
        return ""
    try:
        number = float(value)
        if number.is_integer():
            return f"₹{int(number):,}"
        return f"₹{number:,.0f}"
    except (TypeError, ValueError):
        return str(value)


def ad_hook(ad):
    ad_type = ad.get("ad_type", "")
    headline = ad.get("headline", "")
    if ad_type == "budget_recommendation":
        return headline
    if ad_type == "brand_recommendation":
        return headline
    if ad_type == "price_comparison":
        return headline or "Compare prices before you buy"
    return headline


def build_caption(ad, brand):
    category = display_category(ad.get("category", ""))
    headline = ad.get("headline") or f"Best {category}"
    products = ad.get("products") or []

    prices = []
    for p in products:
        if isinstance(p, dict) and p.get("price_inr") not in (None, ""):
            prices.append(float(p["price_inr"]))

    price_line = ""
    if prices:
        low = min(prices)
        price_line = f"\nStarting from {format_inr(low)}"

    if ad.get("ad_type") == "price_comparison":
        body = (
            f"Compare the same product across Amazon, Flipkart and Croma "
            f"before you buy.{price_line}"
        )
    else:
        body = (
            f"Explore selected products, prices and trusted shopping options "
            f"on {brand['brand_name']}.{price_line}"
        )

    hashtags = [
        "#TrustFolio",
        "#SmartShopping",
        f"#{category.replace(' ', '')}",
        "#CompareAndSave",
    ]

    return {
        "headline": headline,
        "body": body,
        "cta": "Compare on TrustFolio",
        "hashtags": hashtags,
    }


def product_card(product, index, ad):
    return {
        "card_index": index,
        "rank": int(product.get("rank") or index),
        "source_product_id": product.get("product_id") or product.get("source_product_id") or "",
        "title": clean_product_name(product.get("title", ""), 52),
        "full_title": product.get("title", ""),
        "price": product.get("price_inr"),
        "price_display": format_inr(product.get("price_inr")),
        "platform": product.get("platform") or product.get("comparison_platform") or "",
        "image_url": product.get("image_url") or "",
        "click_url": product.get("click_url") or ad.get("landing_url") or "",
        "product_deep_link": product.get("product_deep_link"),
        "rating": product.get("rating"),
        "specifications": product.get("specifications") or {},
        "category": product.get("category") or ad.get("category") or "",
    }


def build_image_spec(ad, template):
    category = display_category(ad.get("category", ""))
    products = ad.get("products") or []
    cards = [product_card(p, i + 1, ad) for i, p in enumerate(products[:5])]

    return {
        "formats": {
            "feed": template["image"]["feed"],
            "square": template["image"]["square"],
        },
        "layout":"hero_headline_product_grid_price_cta",
        "fixed_branding": template["locked_branding"],
        "copy":{
            "headline":ad.get("headline") or f"Best {category}",
            "supporting":"Compare • Save • Shop Smart",
            "cta":"Compare on TrustFolio",
            "website":"trustfolio.in",
        },
        "products":cards,
        "generation_instructions":{
            "use_exact_product_images":True,
            "use_exact_prices":True,
            "do_not_generate_fake_products":True,
            "do_not_change_product_text_facts":True,
            "logo_required":True,
            "logo_asset":template["locked_branding"]["logo_asset"],
        },
    }


def build_carousel_spec(ad, template):
    products = ad.get("products") or []
    cards = []

    for i, product in enumerate(products[: template["carousel"]["max_cards"]], start=1):
        card = product_card(product, i, ad)
        cards.append({
            "card_index":i,
            "headline":card["title"],
            "price":card["price_display"],
            "platform":card["platform"],
            "image_url":card["image_url"],
            "click_url":card["click_url"],
            "deep_link":card["product_deep_link"],
            "source_product_id":product.get("product_id",""),
        })

    return {
        "formats":{
            "width":template["carousel"]["card_width"],
            "height":template["carousel"]["card_height"],
        },
        "fixed_branding":template["locked_branding"],
        "intro_card":{
            "headline":ad.get("headline",""),
            "subheadline":"Compare • Save • Shop Smart",
            "cta":"Swipe to compare",
        },
        "cards":cards,
        "final_card":{
            "headline":"Compare on TrustFolio",
            "website":"trustfolio.in",
            "play_store":template["locked_branding"]["play_store"],
            "click_url":ad.get("landing_url",""),
        },
    }


def build_video_spec(ad, template):
    products = ad.get("products") or []
    short_cards = [product_card(p, i + 1, ad) for i, p in enumerate(products[:5])]
    headline = ad.get("headline","Compare on TrustFolio")

    scenes = [
        {
            "scene":1,
            "start":0,
            "end":2,
            "purpose":"hook",
            "on_screen_text":headline,
            "visual":"Fast product collage with TrustFolio logo lockup",
        },
        {
            "scene":2,
            "start":2,
            "end":8,
            "purpose":"product_reveal",
            "on_screen_text":"Top picks selected from live TrustFolio product data",
            "visual":"Show product cutouts one by one with exact product names and prices",
            "products":short_cards,
        },
        {
            "scene":3,
            "start":8,
            "end":11,
            "purpose":"price_value",
            "on_screen_text":"Compare prices before you buy",
            "visual":"Show Amazon / Flipkart / Croma where present; use only supplied prices",
            "landing_url":ad.get("landing_url",""),
        },
        {
            "scene":4,
            "start":11,
            "end":15,
            "purpose":"cta",
            "on_screen_text":"Compare • Save • Shop Smart",
            "visual":"TrustFolio logo, website and CTA",
            "cta":"Compare on TrustFolio",
            "website":"trustfolio.in",
            "play_store":template["locked_branding"]["play_store"],
        },
    ]

    return {
        "format":{
            "width":template["video"]["width"],
            "height":template["video"]["height"],
            "fps":template["video"]["fps"],
            "duration_seconds":template["video"]["duration_seconds"],
        },
        "fixed_branding":template["locked_branding"],
        "scenes":scenes,
        "generation_guardrails":{
            "exact_product_images":True,
            "exact_prices":True,
            "no_invented_specs":True,
            "no_invented_savings":True,
        },
    }


def build_platform_outputs(ad):
    url = ad.get("landing_url","")
    return {
        "facebook":{
            "feed":"image_feed",
            "carousel":"carousel",
            "reel":"story_reel",
            "story":"story_reel",
            "destination":url,
        },
        "instagram":{
            "feed":"image_feed",
            "carousel":"carousel",
            "reel":"story_reel",
            "story":"story_reel",
            "destination":url,
        },
        "youtube":{
            "shorts":"video_reel",
            "destination":url,
        },
    }


def build_manifest(data, template):
    output_ads = []

    for ad in data.get("ads", []):
        caption = build_caption(ad, template["locked_branding"])
        output_ads.append({
            "ad_id":ad.get("ad_id"),
            "ad_type":ad.get("ad_type"),
            "category":ad.get("category"),
            "headline":ad.get("headline"),
            "landing_url":ad.get("landing_url"),
            "site_ranking_status":ad.get("site_ranking_status") or "unverified",
            "prefill_ready":bool(ad.get("prefill_ready")),
            "ranking_source":ad.get("ranking_source") or "independent_ads_engine",
            "ranking_observed_at":ad.get("ranking_observed_at"),
            "caption":caption,
            "image_ad":build_image_spec(ad, template),
            "carousel_ad":build_carousel_spec(ad, template),
            "video_ad":build_video_spec(ad, template),
            "platform_outputs":build_platform_outputs(ad),
        })

    return {
        "version":"1.0",
        "source":"creative_ad_manifest_v1.json",
        "brand":template["locked_branding"],
        "ads":output_ads,
    }


def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT

    data = load_json(input_path)
    template = load_json(TEMPLATE_PATH)
    result = build_manifest(data, template)

    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 80)
    print("TRUSTFOLIO CREATIVE GENERATOR V1")
    print("=" * 80)
    print("Input :", input_path)
    print("Output:", output_path)
    print("Ads   :", len(result["ads"]))
    print("Image :", "READY")
    print("Carousel:", "READY")
    print("Video :", "READY")
    print("Brand :", result["brand"]["brand_name"])
    print("=" * 80)


if __name__ == "__main__":
    main()
