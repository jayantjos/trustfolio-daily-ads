#!/usr/bin/env python3
import io
import json
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE = Path.home() / "new_scraper"
MANIFEST = BASE / "ads" / "creative_generation_manifest_v1.json"
OUT_DIR = BASE / "ads" / "generated_creatives" / "prototype"
LOGO_URL = "https://www.trustfolio.in/logo.png"

W, H = 1080, 1350
BG = (248, 250, 252)
INK = (17, 24, 39)
MUTED = (95, 105, 120)
WHITE = (255, 255, 255)
ACCENT = (18, 92, 170)
BORDER = (225, 230, 236)


def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def get_bytes(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "TrustFolioCreativeRenderer/1.0"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def load_remote_image(url, box):
    if not url:
        raise ValueError("missing image_url in creative manifest")
    try:
        raw = get_bytes(url)
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        img.thumbnail(box, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", box, (255, 255, 255, 0))
        x = (box[0] - img.width) // 2
        y = (box[1] - img.height) // 2
        canvas.alpha_composite(img, (x, y))
        return canvas
    except Exception as e:
        raise RuntimeError(f"product image download failed: {url} -> {e}") from e


def fit_text(draw, text, max_width, start_size, min_size=18, bold=False):
    size = start_size
    while size > min_size:
        f = font(size, bold)
        if draw.textbbox((0, 0), text, font=f)[2] <= max_width:
            return f
        size -= 1
    return font(min_size, bold)


def draw_card(img, draw, x, y, w, h, product, product_image):
    draw.rounded_rectangle(
        (x, y, x + w, y + h),
        radius=24,
        fill=WHITE,
        outline=BORDER,
        width=2,
    )

    image_x = x + 18
    image_y = y + 18
    image_w = w - 36
    image_h = 185

    draw.rounded_rectangle(
        (image_x, image_y, image_x + image_w, image_y + image_h),
        radius=18,
        fill=(250, 251, 253),
    )
    img.paste(product_image, (image_x, image_y), product_image)

    title = " ".join(str(product.get("title", "")).split())
    if len(title) > 48:
        title = title[:47].rstrip() + "…"

    tf = fit_text(draw, title, w - 36, 21, 16, True)
    draw.multiline_text(
        (x + 18, y + 220),
        title,
        font=tf,
        fill=INK,
        spacing=4,
        anchor="la",
    )

    price = product.get("price_display", "")
    if price:
        pf = fit_text(draw, str(price), w - 36, 28, 20, True)
        draw.text((x + 18, y + h - 78), str(price), font=pf, fill=ACCENT)

    platform = product.get("platform", "")
    if platform:
        draw.text(
            (x + 18, y + h - 40),
            str(platform).title(),
            font=font(15),
            fill=MUTED,
        )


def render(ad):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ad_id = ad["ad_id"]
    out = OUT_DIR / f"{ad_id}_feed_1080x1350.png"

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    draw.text((60, 48), "TrustFolio", font=font(38, True), fill=INK)
    draw.text((60, 95), "Compare • Save • Shop Smart", font=font(20), fill=MUTED)

    try:
        logo = Image.open(io.BytesIO(get_bytes(LOGO_URL))).convert("RGBA")
        logo.thumbnail((150, 70), Image.Resampling.LANCZOS)
        img.paste(logo, (W - 60 - logo.width, 48), logo)
        draw = ImageDraw.Draw(img)
    except Exception as e:
        print(f"[WARN] logo failed: {e}")

    headline = ad.get("headline") or "Smart shopping made simple"
    hf = fit_text(draw, headline, W - 120, 42, 26, True)
    draw.text((60, 145), headline, font=hf, fill=INK)

    products = (ad.get("image_ad") or {}).get("products", [])[:5]
    if not products:
        raise RuntimeError(f"{ad_id}: no products found in image_ad")

    card_w, card_h = 300, 395
    row_y = 235
    positions = [
        (60, row_y),
        (390, row_y),
        (720, row_y),
        (225, row_y + 425),
        (555, row_y + 425),
    ]

    for product, (x, y) in zip(products, positions):
        pimg = load_remote_image(product.get("image_url", ""), (264, 185))
        draw_card(img, draw, x, y, card_w, card_h, product, pimg)

    footer_y = 1115
    draw.line((60, footer_y, W - 60, footer_y), fill=BORDER, width=2)
    draw.text(
        (60, footer_y + 25),
        "Compare on TrustFolio",
        font=font(28, True),
        fill=INK,
    )
    draw.text(
        (60, footer_y + 67),
        "trustfolio.in",
        font=font(20, True),
        fill=ACCENT,
    )
    draw.text(
        (W - 60, footer_y + 70),
        "Prices can change • Verify before checkout",
        font=font(15),
        fill=MUTED,
        anchor="ra",
    )

    img.save(out, quality=95)
    print("=" * 80)
    print("TRUSTFOLIO CREATIVE RENDERER V1")
    print("=" * 80)
    print("AD ID :", ad_id)
    print("TYPE  :", ad.get("ad_type"))
    print("CAT   :", ad.get("category"))
    print("OUT   :", out)
    print("=" * 80)
    return out


def main():
    manifest_path = Path(sys.argv[1]) if len(sys.argv) > 1 else MANIFEST
    ad_id = sys.argv[2] if len(sys.argv) > 2 else ""

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    ads = data.get("ads", [])
    if not ads:
        raise RuntimeError("No ads in creative_generation_manifest_v1.json")

    ad = next((x for x in ads if x.get("ad_id") == ad_id), None) if ad_id else ads[0]
    if ad is None:
        raise RuntimeError(f"Ad ID not found: {ad_id}")

    render(ad)


if __name__ == "__main__":
    main()
