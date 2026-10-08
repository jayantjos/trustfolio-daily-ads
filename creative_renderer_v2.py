#!/usr/bin/env python3
import io
import json
import math
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE = Path.home() / "new_scraper"
MANIFEST = BASE / "ads" / "creative_generation_manifest_v1.json"
OUT_DIR = BASE / "ads" / "generated_creatives" / "prototype_v2"
LOGO_URL = "https://www.trustfolio.in/logo.png"

W, H = 1080, 1350
NAVY = (16, 24, 40)
TEXT = (21, 31, 49)
MUTED = (97, 111, 131)
WHITE = (255, 255, 255)
BLUE = (35, 104, 214)
CYAN = (76, 186, 255)
PALE = (244, 248, 255)
LINE = (220, 228, 240)


def font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def get_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": "TrustFolioCreativeRenderer/2.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def load_product(url, box):
    if not url:
        raise RuntimeError("Missing product image URL")
    raw = get_bytes(url)
    src = Image.open(io.BytesIO(raw)).convert("RGBA")
    src.thumbnail(box, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", box, (255, 255, 255, 0))
    canvas.alpha_composite(src, ((box[0] - src.width) // 2, (box[1] - src.height) // 2))
    return canvas


def fit_one(draw, text, max_width, size, minimum=18, bold=True):
    size = int(size)
    while size >= minimum:
        f = font(size, bold)
        if draw.textbbox((0, 0), text, font=f)[2] <= max_width:
            return f
        size -= 1
    return font(minimum, bold)


def wrap_title(draw, text, max_width, size=21, min_size=14, max_lines=2):
    words = " ".join(str(text).split()).split()
    if not words:
        return "", font(size, True)
    f = fit_one(draw, text, max_width, size, min_size, True)
    lines, cur = [], ""
    for word in words:
        test = (cur + " " + word).strip()
        if draw.textbbox((0, 0), test, font=f)[2] <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while draw.textbbox((0, 0), last + "…", font=f)[2] > max_width and len(last) > 5:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return "\n".join(lines), f


def rounded_gradient_card(base, xy, radius=28):
    x1, y1, x2, y2 = xy
    layer = Image.new("RGBA", (x2-x1, y2-y1), (255,255,255,0))
    px = layer.load()
    for y in range(layer.height):
        t = y / max(1, layer.height-1)
        r = int(255 - 10*t)
        g = int(255 - 9*t)
        b = int(255 - 1*t)
        for x in range(layer.width):
            px[x, y] = (r,g,b,255)
    mask = Image.new("L", layer.size, 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0,0,layer.width-1,layer.height-1), radius=radius, fill=255)
    base.alpha_composite(Image.composite(layer, Image.new("RGBA", layer.size), mask), (x1,y1))


def glow_dot(canvas, cx, cy, radius, color):
    glow = Image.new("RGBA", canvas.size, (0,0,0,0))
    d = ImageDraw.Draw(glow)
    d.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill=color)
    glow = glow.filter(ImageFilter.GaussianBlur(radius=max(12, radius//2)))
    canvas.alpha_composite(glow)


def render(ad):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ad_id = ad["ad_id"]
    out = OUT_DIR / f"{ad_id}_premium_1080x1350.png"

    canvas = Image.new("RGBA", (W, H), PALE + (255,))
    draw = ImageDraw.Draw(canvas)

    # Premium background
    draw.rectangle((0, 0, W, 410), fill=(17, 30, 56, 255))
    glow_dot(canvas, 870, 80, 180, (76, 186, 255, 70))
    glow_dot(canvas, 180, 300, 130, (65, 110, 255, 48))
    draw = ImageDraw.Draw(canvas)

    # Header
    draw.text((58, 42), "TrustFolio", font=font(34, True), fill=WHITE)
    draw.text((58, 83), "Compare • Save • Shop Smart", font=font(18), fill=(218, 229, 247))
    draw.text((W-58, 58), "SMART SHOPPING", font=font(15, True), fill=(184, 213, 247), anchor="ra")

    headline = ad.get("headline") or "Smart shopping made simple"
    words = headline.split()
    if len(headline) > 30:
        # Keep headline compact but preserve exact text.
        hf = fit_one(draw, headline, 900, 40, 28, True)
    else:
        hf = fit_one(draw, headline, 900, 44, 30, True)
    draw.text((58, 138), headline, font=hf, fill=WHITE)

    products = (ad.get("image_ad") or {}).get("products", [])[:5]
    if not products:
        raise RuntimeError(f"{ad_id}: no products in manifest")

    prices = [float(p["price"]) for p in products if p.get("price") not in (None, "")]
    low = min(prices) if prices else None
    chips_y = 238

    chips = [
        ("5 curated picks", (255,255,255), (33,57,94)),
        (f"Starting {products[0].get('price_display','')}" if low is None else f"From ₹{int(low):,}", (221,241,255), (23,62,109)),
        ("Live price data", (255,255,255), (33,57,94)),
    ]
    x = 58
    for label, fill, txt in chips:
        tw = draw.textbbox((0,0), label, font=font(16, True))[2] + 36
        draw.rounded_rectangle((x, chips_y, x+tw, chips_y+42), radius=21, fill=fill)
        draw.text((x+18, chips_y+11), label, font=font(16, True), fill=txt)
        x += tw + 12

    # Content panel
    draw.rounded_rectangle((40, 360, W-40, 1265), radius=34, fill=(255,255,255), outline=LINE, width=2)

    # Product cards: 3 top, 2 large bottom
    positions = [
        (68, 410, 314, 730),
        (383, 410, 631, 730),
        (700, 410, 1012, 730),
        (195, 755, 523, 1115),
        (557, 755, 885, 1115),
    ]

    for idx, (product, pos) in enumerate(zip(products, positions), start=1):
        x1,y1,x2,y2 = pos
        rounded_gradient_card(canvas, pos, 28)
        draw = ImageDraw.Draw(canvas)

        # Number marker
        draw.ellipse((x1+18,y1+18,x1+52,y1+52), fill=(17,30,56))
        draw.text((x1+35,y1+35), str(idx), font=font(15, True), fill=WHITE, anchor="mm")

        # Product visual
        img_box = (x2-x1-36, 175 if idx <= 3 else 205)
        pimg = load_product(product.get("image_url",""), img_box)
        ix = x1 + (x2-x1-img_box[0])//2
        iy = y1 + 58
        draw.rounded_rectangle((x1+18, y1+58, x2-18, y1+58+img_box[1]), radius=22, fill=(247,249,253))
        canvas.alpha_composite(pimg, (ix, iy))
        draw = ImageDraw.Draw(canvas)

        title = product.get("title","")
        title_text, tf = wrap_title(draw, title, x2-x1-36, 19 if idx <=3 else 20, 14, 2)
        draw.multiline_text((x1+18, y1+58+img_box[1]+18), title_text, font=tf, fill=TEXT, spacing=2)

        price = product.get("price_display","")
        if price:
            pf = fit_one(draw, str(price), x2-x1-36, 29, 22, True)
            draw.text((x1+18, y2-66), str(price), font=pf, fill=BLUE)

        platform = str(product.get("platform","")).title()
        if platform:
            draw.rounded_rectangle((x1+18, y2-36, x1+18+max(80, draw.textbbox((0,0), platform, font=font(14, True))[2]+24), y2-12), radius=12, fill=(239,245,255))
            draw.text((x1+30, y2-30), platform, font=font(14, True), fill=(41,75,130))

    # CTA band
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((68, 1160, W-68, 1240), radius=26, fill=(17,30,56))
    draw.text((96, 1182), "Compare the picks before you buy", font=font(24, True), fill=WHITE)
    draw.text((W-96, 1184), "trustfolio.in", font=font(21, True), fill=(129, 205, 255), anchor="ra")

    # Footer
    draw.text((58, 1280), "TrustFolio", font=font(22, True), fill=TEXT)
    draw.text((58, 1312), "Prices can change • Verify before checkout", font=font(14), fill=MUTED)
    draw.text((W-58, 1300), "Compare • Save • Shop Smart", font=font(15, True), fill=BLUE, anchor="ra")

    # Flatten to RGB
    final = Image.new("RGB", canvas.size, WHITE)
    final.paste(canvas, mask=canvas.getchannel("A"))
    final.save(out, quality=96, optimize=True)
    print("=" * 80)
    print("TRUSTFOLIO CREATIVE RENDERER V2")
    print("=" * 80)
    print("AD ID :", ad_id)
    print("TYPE  :", ad.get("ad_type"))
    print("CAT   :", ad.get("category"))
    print("OUT   :", out)
    print("=" * 80)


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else MANIFEST
    ad_id = sys.argv[2] if len(sys.argv) > 2 else ""
    data = json.loads(path.read_text(encoding="utf-8"))
    ad = next((x for x in data.get("ads", []) if x.get("ad_id") == ad_id), None) if ad_id else (data.get("ads") or [None])[0]
    if not ad:
        raise SystemExit("No ad found")
    render(ad)


if __name__ == "__main__":
    main()
