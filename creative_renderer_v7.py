#!/usr/bin/env python3
"""
TrustFolio master infographic renderer V7.

Input:
  trustfolio_infographic_payload_v1.json

The payload is the single daily data contract. This wrapper adapts it to the
reference-style renderer and adds a fixed cursor/click cue over the CTA.
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

BASE = Path.home() / "new_scraper"
DEFAULT_INPUT = BASE / "ads" / "trustfolio_infographic_payload_v1.json"

sys.path.insert(0, str(BASE / "ads"))
import creative_renderer_v6 as renderer

renderer.VERSION = "V7"
OUT_DIR = BASE / "ads" / "generated_creatives" / "feed"


def money(v):
    if v in (None, ""):
        return ""
    try:
        return f"₹{float(v):,.0f}"
    except (TypeError, ValueError):
        return str(v)


def as_spec_dict(items):
    out = {}
    for i, item in enumerate(items or [], start=1):
        text = str(item).strip()
        if not text:
            continue
        if ": " in text:
            k, v = text.split(": ", 1)
        else:
            k, v = f"Feature {i}", text
        out[k] = v
    return out


def adapt_ad(payload_ad):
    products = []
    for p in payload_ad.get("products", [])[:5]:
        products.append({
            "image_url": p.get("image_url") or "",
            "full_title": p.get("name") or "",
            "title": p.get("name") or "",
            "price": p.get("price_inr"),
            "price_display": money(p.get("price_inr")),
            "platform": p.get("retailer") or "",
            "rating": p.get("verified_rating"),
            "specifications": as_spec_dict(p.get("key_specs")),
        })

    metadata = payload_ad.get("metadata") or {}
    return {
        "ad_id": payload_ad.get("source_ad_id") or "unknown",
        "ad_type": payload_ad.get("source_ad_type") or "budget_recommendation",
        "category": str(metadata.get("campaign_category") or "").lower().replace(" ", "-"),
        "headline": metadata.get("campaign_title") or "",
        "image_ad": {"products": products},
        "landing_url": payload_ad.get("landing_url") or "",
    }


def render(payload_ad):
    global OUT_DIR
    adapted = adapt_ad(payload_ad)
    renderer.OUT_DIR = OUT_DIR
    renderer.VERSION = "V7"
    renderer.render(adapted)
    output = OUT_DIR / f"{adapted["ad_id"]}_premium_1080x1350.png"
    add_cursor(output)
    return adapted.get("ad_id", "")


def add_cursor(path):
    img = Image.open(path).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # Fixed click cue near the CTA, matching the approved reference treatment.
    points = [
        (565, 1248),
        (595, 1275),
        (581, 1275),
        (590, 1308),
        (577, 1312),
        (567, 1280),
        (557, 1292),
    ]
    draw.polygon(points, fill=(255, 255, 255, 255), outline=(8, 20, 45, 255))

    # Yellow click rays.
    rays = [
        ((603, 1280), (620, 1265)),
        ((607, 1292), (629, 1290)),
        ((596, 1302), (610, 1320)),
    ]
    for a, b in rays:
        draw.line((a[0], a[1], b[0], b[1]), fill=(255, 217, 35, 255), width=5)

    out = img.convert("RGB")
    out.save(path, quality=96, optimize=True)


def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    ad_id = sys.argv[2] if len(sys.argv) > 2 else ""

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    ads = payload.get("ads") or []
    if not ads:
        raise SystemExit("No ads in infographic payload.")

    item = (
        next((x for x in ads if x.get("source_ad_id") == ad_id), None)
        if ad_id
        else ads[0]
    )
    if not item:
        raise SystemExit(f"Ad ID not found: {ad_id}")

    ad = adapt_ad(item)

    renderer.render(ad)
    output = renderer.OUT_DIR / f"{ad['ad_id']}_premium_1080x1350.png"
    add_cursor(output)

    print()
    print("TRUSTFOLIO CREATIVE RENDERER V7")
    print("SOURCE  :", input_path)
    print("AD ID   :", ad["ad_id"])
    print("OUTPUT  :", output)
    print("CURSOR  : ENABLED")
    print("=" * 80)


if __name__ == "__main__":
    main()
