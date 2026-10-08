#!/usr/bin/env python3
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE = Path.home() / "new_scraper"
MANIFEST = BASE / "ads" / "creative_generation_manifest_v1.json"
VERSION = "V4"
OUT_DIR = BASE / "ads" / "generated_creatives" / "feed"
LOGO_URL = "https://www.trustfolio.in/logo.png"

W, H = 1080, 1350

NAVY = (8, 25, 60)
NAVY_2 = (18, 42, 91)
BLUE = (37, 117, 240)
CYAN = (54, 205, 255)
PURPLE = (104, 35, 245)
PURPLE_DARK = (61, 20, 170)
PINK = (245, 71, 182)
YELLOW = (255, 218, 40)
GOLD = (255, 183, 47)
WHITE = (255, 255, 255)
INK = (18, 29, 49)
MUTED = (83, 100, 126)
PALE = (238, 247, 255)
LINE = (219, 230, 245)


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
    if not url:
        raise RuntimeError("Missing URL")
    req = urllib.request.Request(
        url, headers={"User-Agent": "TrustFolioCreativeRenderer/4.0"}
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def load_image(url, box):
    raw = get_bytes(url)
    src = Image.open(io.BytesIO(raw)).convert("RGBA")
    src.thumbnail(box, Image.Resampling.LANCZOS)
    layer = Image.new("RGBA", box, (255, 255, 255, 0))
    layer.alpha_composite(src, ((box[0] - src.width) // 2, (box[1] - src.height) // 2))
    return layer


def fit_text(draw, text, width, start, minimum=14, bold=True):
    text = str(text or "")
    for size in range(start, minimum - 1, -1):
        f = font(size, bold)
        if draw.textbbox((0, 0), text, font=f)[2] <= width:
            return f
    return font(minimum, bold)


def wrap_lines(draw, text, width, start=18, minimum=12, max_lines=2):
    words = " ".join(str(text or "").split()).split()
    if not words:
        return "", font(minimum, True)

    for size in range(start, minimum - 1, -1):
        f = font(size, True)
        lines = []
        current = ""
        for word in words:
            test = (current + " " + word).strip()
            if draw.textbbox((0, 0), test, font=f)[2] <= width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)

        if len(lines) <= max_lines:
            return "\n".join(lines), f

    f = font(minimum, True)
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        if draw.textbbox((0, 0), test, font=f)[2] <= width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    lines = lines[:max_lines]
    if len(lines) == max_lines and lines:
        last = lines[-1]
        while draw.textbbox((0, 0), last + "…", font=f)[2] > width and len(last) > 4:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return "\n".join(lines), f


def draw_glow(canvas, cx, cy, radius, rgba):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=rgba)
    layer = layer.filter(ImageFilter.GaussianBlur(max(10, radius // 3)))
    canvas.alpha_composite(layer)


def rounded_gradient(canvas, box, top, bottom, radius=28):
    x1, y1, x2, y2 = box
    ww, hh = x2 - x1, y2 - y1
    layer = Image.new("RGBA", (ww, hh), (0, 0, 0, 0))
    px = layer.load()
    for y in range(hh):
        t = y / max(1, hh - 1)
        c = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)) + (255,)
        for x in range(ww):
            px[x, y] = c
    mask = Image.new("L", (ww, hh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, ww - 1, hh - 1), radius=radius, fill=255)
    canvas.alpha_composite(Image.composite(layer, Image.new("RGBA", (ww, hh)), mask), (x1, y1))


def money(value):
    if value in (None, ""):
        return ""
    try:
        return f"₹{float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


def specs_for(product, max_items=3):
    specs = product.get("specifications") or {}
    if not isinstance(specs, dict):
        return []

    priority = [
        "display", "screen size", "size", "battery", "ram", "storage",
        "capacity", "power", "watt", "resolution", "connectivity",
        "processor", "refresh rate", "type",
    ]

    pairs = []
    normalized = [
        (str(k).strip(), str(v).strip())
        for k, v in specs.items()
        if v not in (None, "")
    ]
    normalized = [(k, v) for k, v in normalized if len(v) <= 65]

    for needle in priority:
        for k, v in normalized:
            if needle in k.lower() and (k, v) not in pairs:
                pairs.append((k, v))
                if len(pairs) >= max_items:
                    return pairs

    for pair in normalized:
        if pair not in pairs:
            pairs.append(pair)
        if len(pairs) >= max_items:
            break

    return pairs


def product_title(product):
    return product.get("full_title") or product.get("title") or ""


def price_value(product):
    try:
        return float(product.get("price"))
    except (TypeError, ValueError):
        return None


def parse_budget_headline(headline):
    m = re.match(r"^(.*?)(?:\s+Under\s+)(₹[\d,]+)$", str(headline or ""), re.I)
    if not m:
        return str(headline or ""), None
    return m.group(1).strip(), m.group(2)


def draw_price_badge(draw, x, y, w, price):
    draw.rounded_rectangle((x, y, x + w, y + 52), radius=17, fill=YELLOW)
    f = fit_text(draw, price, w - 18, 28, 20, True)
    draw.text((x + w / 2, y + 26), price, font=f, fill=INK, anchor="mm")


def draw_platform(draw, x, y, label):
    text = str(label or "").title()
    if not text:
        return
    f = font(13, True)
    tw = draw.textbbox((0, 0), text, font=f)[2] + 24
    fill = {
        "Amazon": (255, 247, 233),
        "Flipkart": (234, 245, 255),
        "Croma": (231, 255, 245),
    }.get(text, (238, 245, 255))
    draw.rounded_rectangle((x, y, x + tw, y + 28), radius=14, fill=fill)
    draw.text((x + 12, y + 6), text, font=f, fill=(39, 67, 111))


def draw_rank_badge(draw, cx, cy, number, fill):
    draw.ellipse((cx - 23, cy - 23, cx + 23, cy + 23), fill=fill, outline=WHITE, width=3)
    draw.text((cx, cy), str(number), font=font(18, True), fill=WHITE, anchor="mm")


def draw_small_product(canvas, product, box, number):
    x1, y1, x2, y2 = box
    rounded_gradient(canvas, box, (255, 255, 255), (239, 247, 255), 28)
    draw = ImageDraw.Draw(canvas)

    draw_rank_badge(draw, x1 + 28, y1 + 28, number, NAVY)

    img_h = 155
    draw.rounded_rectangle((x1 + 16, y1 + 55, x2 - 16, y1 + 55 + img_h), radius=22, fill=(248, 250, 254))
    pimg = load_image(product["image_url"], (x2 - x1 - 32, img_h))
    canvas.alpha_composite(pimg, (x1 + 16, y1 + 55))
    draw = ImageDraw.Draw(canvas)

    title, tf = wrap_lines(draw, product_title(product), x2 - x1 - 32, start=17, minimum=12, max_lines=2)
    draw.multiline_text((x1 + 16, y1 + 222), title, font=tf, fill=INK, spacing=2)

    price = product.get("price_display") or money(product.get("price"))
    draw_price_badge(draw, x1 + 16, y2 - 66, x2 - x1 - 32, price)
    draw_platform(draw, x1 + 16, y2 - 32, product.get("platform"))


def draw_featured(canvas, product, box, number, featured_label):
    x1, y1, x2, y2 = box
    rounded_gradient(canvas, box, (35, 109, 218), (7, 46, 119), 34)
    draw = ImageDraw.Draw(canvas)

    draw.ellipse((x1 + 8, y1 - 25, x1 + 74, y1 + 41), fill=YELLOW, outline=WHITE, width=4)
    draw.text((x1 + 41, y1 + 9), str(number), font=font(24, True), fill=INK, anchor="mm")

    draw.rounded_rectangle((x1 + 40, y1 + 20, x2 - 40, y1 + 56), radius=18, fill=(255, 255, 255, 235))
    draw.text((x1 + (x2 - x1) / 2, y1 + 28), featured_label, font=font(14, True), fill=PURPLE_DARK, anchor="ma")

    img_h = 265
    draw.rounded_rectangle((x1 + 35, y1 + 66, x2 - 35, y1 + 66 + img_h), radius=28, fill=(243, 248, 255))
    pimg = load_image(product["image_url"], (x2 - x1 - 70, img_h))
    canvas.alpha_composite(pimg, (x1 + 35 + (x2 - x1 - 70 - pimg.width) // 2, y1 + 66))
    draw = ImageDraw.Draw(canvas)

    title, tf = wrap_lines(draw, product_title(product), x2 - x1 - 70, start=22, minimum=14, max_lines=2)
    draw.multiline_text((x1 + 35, y1 + 349), title, font=tf, fill=WHITE, spacing=2, anchor="la")

    pairs = specs_for(product, 3)
    sy = y1 + 398
    col_w = (x2 - x1 - 85) // 3 if len(pairs) else 0
    for i, (k, v) in enumerate(pairs):
        short = f"{k.title()}: {v}"
        if len(short) > 25:
            short = short[:24] + "…"
        draw.text((x1 + 35 + i * col_w, sy), short, font=font(11, True), fill=(214, 229, 255))

    price = product.get("price_display") or money(product.get("price"))
    draw_price_badge(draw, x1 + 55, y2 - 78, x2 - x1 - 110, price)
    draw_platform(draw, x1 + 55, y2 - 36, product.get("platform"))


def render(ad):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ad_id = ad["ad_id"]
    out = OUT_DIR / f"{ad_id}_premium_1080x1350.png"

    canvas = Image.new("RGBA", (W, H), (226, 242, 255, 255))
    draw = ImageDraw.Draw(canvas)

    # Bright editorial background inspired by the approved reference.
    draw.rectangle((0, 0, W, H), fill=(232, 245, 255))
    draw_glow(canvas, 160, 240, 260, (77, 185, 255, 110))
    draw_glow(canvas, 905, 300, 300, (142, 82, 255, 90))
    draw_glow(canvas, 510, 760, 330, (255, 255, 255, 130))
    draw_glow(canvas, 950, 1120, 180, (50, 214, 255, 80))

    # Soft geometric waves.
    draw = ImageDraw.Draw(canvas)
    draw.pieslice((-230, -240, 620, 520), 10, 170, fill=(255, 255, 255, 120))
    draw.pieslice((600, 210, 1260, 900), 180, 345, fill=(208, 232, 255, 145))
    draw.ellipse((-80, 875, 320, 1275), fill=(207, 239, 255, 125))

    # Decorative accent shards.
    for pts, fill in [
        ([(580, 70), (675, 30), (632, 105)], (255, 190, 24, 230)),
        ([(700, 48), (820, 28), (745, 92)], (109, 45, 242, 220)),
        ([(470, 180), (520, 120), (535, 205)], (244, 68, 187, 210)),
        ([(850, 115), (920, 70), (905, 145)], (255, 202, 26, 220)),
    ]:
        draw.polygon(pts, fill=fill)

    # Logo and top brand line.
    try:
        logo = load_image(LOGO_URL, (115, 62))
        canvas.alpha_composite(logo, (48, 28))
        draw = ImageDraw.Draw(canvas)
        draw.text((173, 36), "TrustFolio", font=font(42, True), fill=INK)
    except Exception:
        draw.text((52, 34), "TrustFolio", font=font(42, True), fill=INK)

    draw.text((174, 87), "Compare • Save • Shop Smart", font=font(18), fill=MUTED)
    draw.text((1020, 43), "SMART", font=font(18, True), fill=PURPLE_DARK, anchor="ra")
    draw.text((1020, 68), "SHOPPING", font=font(18, True), fill=BLUE, anchor="ra")

    headline = str(ad.get("headline") or "")
    left, budget = parse_budget_headline(headline)

    # Main headline ribbon.
    draw.rounded_rectangle((425, 108, 1030, 236), radius=34, fill=(83, 27, 208, 235), outline=(124, 55, 255, 245), width=4)
    draw.rounded_rectangle((438, 121, 1017, 223), radius=28, fill=(42, 18, 114, 210))
    hf = fit_text(draw, left, 535, 34, 23, True)
    draw.text((725, 151), left, font=hf, fill=WHITE, anchor="ma")

    if budget:
        bf = fit_text(draw, f"Under {budget}", 520, 52, 34, True)
        draw.text((728, 205), f"Under {budget}", font=bf, fill=YELLOW, anchor="ma")
    else:
        bf = fit_text(draw, headline, 720, 46, 28, True)
        draw.text((720, 181), headline, font=bf, fill=YELLOW, anchor="ma")

    sub = "Top 5 Picks • Real Product Images • Live Prices"
    if ad.get("ad_type") == "price_comparison":
        sub = "Compare the same product across major platforms"
    draw.rounded_rectangle((405, 246, 1035, 292), radius=23, fill=YELLOW)
    draw.text((720, 270), sub, font=font(17, True), fill=INK, anchor="mm")

    # Benefits panel.
    benefits = [
        ("COMPARE PRICES", "Across Top Websites", BLUE),
        ("LATEST MODELS", "Real Price Data", (8, 175, 132)),
        ("TOP PICKS", "Selected from TrustFolio data", PURPLE),
        ("BEST DEALS", "Within Your Budget", (28, 116, 235)),
    ]
    y = 125
    for title, subtitle, c in benefits:
        draw.rounded_rectangle((48, y, 350, y + 61), radius=29, fill=(255, 255, 255, 225), outline=(214, 229, 247), width=2)
        draw.ellipse((58, y + 9, 102, y + 53), fill=c)
        draw.text((80, y + 31), "✓", font=font(23, True), fill=WHITE, anchor="mm")
        draw.text((116, y + 14), title, font=font(14, True), fill=INK)
        draw.text((116, y + 34), subtitle, font=font(11), fill=MUTED)
        y += 68

    products = (ad.get("image_ad") or {}).get("products", [])[:5]
    if not products:
        raise RuntimeError(f"{ad_id}: no products in manifest")

    # Use lowest-priced product as the factual featured/best-price pick for budget ads.
    featured_index = 0
    vals = [(i, price_value(p)) for i, p in enumerate(products)]
    valid = [(i, v) for i, v in vals if v is not None]
    if valid and ad.get("ad_type") != "price_comparison":
        featured_index = min(valid, key=lambda x: x[1])[0]

    featured = products[featured_index]
    others = [p for i, p in enumerate(products) if i != featured_index]

    # Main podium area.
    draw.rounded_rectangle((38, 355, 1042, 1248), radius=42, fill=(255, 255, 255, 225), outline=(220, 231, 245), width=2)

    # Side and center cards.
    side_left = others[0] if len(others) > 0 else None
    side_right = others[1] if len(others) > 1 else None
    bottom_left = others[2] if len(others) > 2 else None
    bottom_right = others[3] if len(others) > 3 else None

    if side_left:
        draw_small_product(canvas, side_left, (62, 420, 323, 805), 2)
    if side_right:
        draw_small_product(canvas, side_right, (757, 420, 1018, 805), 3)

    draw_featured(canvas, featured, (346, 408, 734, 930), featured_index + 1, "BEST PRICE" if featured_index != 0 or ad.get("ad_type") != "brand_recommendation" else "FEATURED PICK")

    if bottom_left:
        draw_small_product(canvas, bottom_left, (137, 848, 493, 1168), 4)
    if bottom_right:
        draw_small_product(canvas, bottom_right, (587, 848, 943, 1168), 5)

    # Final benefit strip.
    draw.rounded_rectangle((46, 1178, 1034, 1238), radius=27, fill=NAVY)
    items = [
        ("₹", "Compare Prices"),
        ("✓", "Find Better Deals"),
        ("★", "Latest Products"),
        ("✓", "No Login"),
    ]
    xs = [102, 345, 595, 840]
    for (icon, label), xx in zip(items, xs):
        draw.ellipse((xx - 23, 1186, xx + 23, 1232), fill=(245, 77, 177) if icon == "₹" else (255, 196, 38) if icon == "✓" else PURPLE)
        draw.text((xx, 1209), icon, font=font(20, True), fill=WHITE, anchor="mm")
        draw.text((xx + 38, 1196), label, font=font(13, True), fill=WHITE)
        draw.text((xx + 38, 1215), "TrustFolio", font=font(10), fill=(186, 203, 231))

    # Strong CTA.
    draw.rounded_rectangle((60, 1256, 670, 1320), radius=30, fill=YELLOW)
    draw.text((365, 1288), "Compare Now on TrustFolio  →", font=font(24, True), fill=INK, anchor="mm")
    draw.text((1015, 1268), "trustfolio.in", font=font(26, True), fill=NAVY, anchor="ra")
    draw.text((1015, 1300), "Smart Shopping for a Smarter You", font=font(12), fill=MUTED, anchor="ra")

    final = Image.new("RGB", (W, H), WHITE)
    final.paste(canvas, mask=canvas.getchannel("A"))
    final.save(out, quality=96, optimize=True)

    print("=" * 80)
    print(f"TRUSTFOLIO CREATIVE RENDERER {VERSION}")
    print("=" * 80)
    print("AD ID :", ad_id)
    print("TYPE  :", ad.get("ad_type"))
    print("CAT   :", ad.get("category"))
    print("OUT   :", out)
    print("=" * 80)


def main():
    manifest_path = Path(sys.argv[1]) if len(sys.argv) > 1 else MANIFEST
    ad_id = sys.argv[2] if len(sys.argv) > 2 else ""

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    ads = data.get("ads", [])
    if not ads:
        raise SystemExit("No ads found")

    ad = next((x for x in ads if x.get("ad_id") == ad_id), None) if ad_id else ads[0]
    if not ad:
        raise SystemExit(f"Ad ID not found: {ad_id}")

    render(ad)


if __name__ == "__main__":
    main()
