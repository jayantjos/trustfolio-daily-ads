#!/usr/bin/env python3
import json
import os
from pathlib import Path

BASE = Path.home() / "new_scraper"
INPUT = BASE / "ads" / "creative_generation_manifest_v1.json"
OUTPUT = BASE / "ads" / "social_post_manifest_v1.json"

MEDIA_BASE = os.getenv(
    "TRUSTFOLIO_PUBLIC_MEDIA_BASE_URL",
    "https://media.trustfolio.in",
).rstrip("/")


def money(v):
    if v in (None, ""):
        return ""
    try:
        return f"₹{float(v):,.0f}"
    except (TypeError, ValueError):
        return str(v)


def category_name(category):
    return {
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
    }.get(category, str(category).replace("-", " ").title())


def build_media_url(ad_id):
    return f"{MEDIA_BASE}/feed/{ad_id}_premium_1080x1350.png"


def hashtags(ad):
    cat = category_name(ad.get("category", ""))
    compact = "".join(cat.split())
    tags = ["#TrustFolio", "#SmartShopping", f"#{compact}", "#CompareAndSave"]
    if ad.get("ad_type") == "price_comparison":
        tags.append("#PriceComparison")
    return tags


def lowest_price(products):
    if isinstance(products, dict):
        products = list(products.values())

    values = []
    for p in products or []:
        if isinstance(p, dict) and p.get("price_inr") not in (None, ""):
            try:
                values.append(float(p["price_inr"]))
            except (TypeError, ValueError):
                pass
    return min(values) if values else None


def build_copy(ad):
    ad_type = ad.get("ad_type", "")
    headline = ad.get("headline") or f"Best {category_name(ad.get('category', ''))}"
    category = category_name(ad.get("category", ""))
    products = ad.get("products") or []
    price = lowest_price(products)

    if ad_type == "price_comparison":
        saving = ad.get("saving_inr")
        saving_pct = ad.get("saving_percent")
        best_price = ad.get("best_price_inr")
        platform = str(ad.get("best_platform") or "").title()

        extra = ""
        if saving not in (None, ""):
            extra = f" Listed-price difference: {money(saving)}"
            if saving_pct not in (None, ""):
                extra += f" ({float(saving_pct):.0f}%)."

        body = (
            "Same product ko major shopping platforms par compare karein "
            "aur buy karne se pehle best listed price check karein. "
            f"Best listed price: {money(best_price)}"
            f"{' on ' + platform if platform else ''}.{extra}"
        )
        ig = (
            f"{headline}\n\n"
            "Amazon, Flipkart aur Croma listings ko compare karke "
            f"better buying decision lein. Best listed price: {money(best_price)}"
            f"{' on ' + platform if platform else ''}.{extra}\n\n"
            "Compare before you buy."
        )
        yt_desc = (
            f"{headline}.\n\n"
            "TrustFolio par Amazon, Flipkart aur Croma listings compare karein. "
            f"Best listed price: {money(best_price)}"
            f"{' on ' + platform if platform else ''}.{extra}\n\n"
            "Compare • Save • Shop Smart\n"
            "https://www.trustfolio.in/\n"
            "https://play.google.com/store/apps/details?id=com.trustfolio.app"
        )
    else:
        start = f" Starting from {money(price)}." if price is not None else ""
        body = (
            f"{headline}. "
            f"TrustFolio par selected {category.lower()} products, prices aur shopping options compare karein."
            f"{start}"
        )
        if ad_type == "brand_recommendation" and ad.get("brand"):
            body = (
                f"Looking for {ad.get('brand')} {category.lower()}? "
                f"{len(products)} selected picks ko compare karein.{start}"
            )

        ig = f"{headline}\n\n{body}\n\nCompare • Save • Shop Smart."
        yt_desc = (
            f"{headline}.\n\n"
            f"{body}\n\n"
            "Compare • Save • Shop Smart\n"
            "https://www.trustfolio.in/\n"
            "https://play.google.com/store/apps/details?id=com.trustfolio.app"
        )

    # Pass the campaign URL through to organic captions without claiming it is
    # a clickable Instagram feed link; use a correctly configured bio/Story CTA.
    campaign_url = str(ad.get("landing_url") or "https://www.trustfolio.in/")
    ig = ig + "\n\nTrustFolio search: " + campaign_url

    fb = (
        f"{body}\n\n"
        f"Compare on TrustFolio: {ad.get('landing_url', 'https://www.trustfolio.in/')}"
    )

    return {
        "facebook": {
            "format": "feed_post",
            "text": fb,
            "headline": headline,
            "cta": "Learn More",
            "destination_url": ad.get("landing_url", ""),
        },
        "instagram": {
            "format": "feed_post",
            "caption": ig,
            "hashtags": hashtags(ad),
            "destination_url": ad.get("landing_url", ""),
        },
        "instagram_reel": {
            "format": "reel",
            "caption": ig,
            "hashtags": hashtags(ad),
            "destination_url": ad.get("landing_url", ""),
            "media_status": "video_renderer_pending",
        },
        "facebook_reel": {
            "format": "reel",
            "text": fb,
            "headline": headline,
            "destination_url": ad.get("landing_url", ""),
            "media_status": "video_renderer_pending",
        },
        "youtube_shorts": {
            "format": "short",
            "title": headline[:100],
            "description": yt_desc,
            "hashtags": hashtags(ad),
            "destination_url": ad.get("landing_url", ""),
            "media_status": "video_renderer_pending",
        },
    }


def main():
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    brand = data.get("brand", {})
    output_ads = []

    for ad in data.get("ads", []):
        ad_id = ad.get("ad_id")
        image_url = build_media_url(ad_id)

        posts = build_copy(ad)
        for platform in posts.values():
            if platform.get("media_status"):
                continue
            platform["media_url"] = image_url
            platform["media_type"] = "image"

        output_ads.append({
            "ad_id": ad_id,
            "ad_type": ad.get("ad_type"),
            "category": ad.get("category"),
            "headline": ad.get("headline"),
            "landing_url": ad.get("landing_url"),
            "media": {
                "feed_image": {
                    "url": image_url,
                    "type": "image/png",
                    "public": True,
                },
                "video": {
                    "status": "not_rendered",
                },
            },
            "posts": posts,
        })

    result = {
        "version": "1.0",
        "brand": {
            "name": brand.get("brand_name") or brand.get("name") or "TrustFolio",
            "website": brand.get("website") or brand.get("website_url") or "https://www.trustfolio.in/",
            "play_store": brand.get("play_store") or brand.get("play_store_url") or "",
        },
        "generated_from": "creative_generation_manifest_v1.json",
        "media_base_url": MEDIA_BASE,
        "ads": output_ads,
    }

    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 88)
    print("TRUSTFOLIO SOCIAL POST MANIFEST V1")
    print("=" * 88)
    print("Ads:", len(output_ads))
    print("Platforms:", "Facebook, Instagram, Instagram Reel, Facebook Reel, YouTube Shorts")
    print("Output:", OUTPUT)
    print("=" * 88)


if __name__ == "__main__":
    main()
