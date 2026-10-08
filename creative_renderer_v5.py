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
VERSION = "V5"
OUT_DIR = BASE / "ads" / "generated_creatives" / "feed"
LOGO_URL = "https://www.trustfolio.in/logo.png"

W, H = 1080, 1350

# Locked TrustFolio master palette/layout.
NAVY = (5, 25, 61)
NAVY_2 = (14, 53, 116)
BLUE = (30, 111, 235)
CYAN = (36, 208, 255)
PURPLE = (100, 34, 240)
PINK = (246, 67, 183)
YELLOW = (255, 217, 36)
WHITE = (255, 255, 255)
INK = (14, 30, 57)
MUTED = (81, 101, 129)
PALE = (229, 244, 255)
LINE = (211, 228, 244)


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
    req = urllib.request.Request(url, headers={"User-Agent": "TrustFolioCreativeRenderer/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def load_image(url, box):
    raw = get_bytes(url)
    src = Image.open(io.BytesIO(raw)).convert("RGBA")
    src.thumbnail(box, Image.Resampling.LANCZOS)
    out = Image.new("RGBA", box, (255, 255, 255, 0))
    out.alpha_composite(src, ((box[0] - src.width) // 2, (box[1] - src.height) // 2))
    return out


def fit(draw, text, width, start, minimum=12, bold=True):
    text = str(text or "")
    for size in range(start, minimum - 1, -1):
        f = font(size, bold)
        if draw.textbbox((0, 0), text, font=f)[2] <= width:
            return f
    return font(minimum, bold)


def wrap(draw, text, width, start=18, minimum=12, max_lines=2):
    words = " ".join(str(text or "").split()).split()
    if not words:
        return "", font(minimum, True)

    chosen = font(minimum, True)
    best = None
    for size in range(start, minimum - 1, -1):
        f = font(size, True)
        lines, cur = [], ""
        for word in words:
            test = (cur + " " + word).strip()
            if draw.textbbox((0, 0), test, font=f)[2] <= width:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        if len(lines) <= max_lines:
            best = ("\n".join(lines), f)
            break
    if best:
        return best

    f = chosen
    lines, cur = [], ""
    for word in words:
        test = (cur + " " + word).strip()
        if draw.textbbox((0, 0), test, font=f)[2] <= width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    lines = lines[:max_lines]
    if len(lines) == max_lines:
        last = lines[-1]
        while draw.textbbox((0, 0), last + "…", font=f)[2] > width and len(last) > 4:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return "\n".join(lines), f


def money(value):
    if value in (None, ""):
        return ""
    try:
        return f"₹{float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


def price_value(p):
    try:
        return float(p.get("price"))
    except (TypeError, ValueError):
        return None


def parse_budget(headline):
    m = re.match(r"^(.*?)(?:\s+Under\s+)(₹[\d,]+)$", str(headline or ""), re.I)
    if not m:
        return str(headline or ""), None
    return m.group(1).strip(), m.group(2)


def glow(canvas, cx, cy, radius, rgba):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill=rgba)
    layer = layer.filter(ImageFilter.GaussianBlur(max(12, radius // 3)))
    canvas.alpha_composite(layer)


def product_specs(product, limit=3):
    specs = product.get("specifications") or {}
    if not isinstance(specs, dict):
        return []

    priority = [
        "display", "screen size", "size", "battery", "ram", "storage",
        "resolution", "connectivity", "processor", "refresh rate", "capacity",
        "power", "watt", "type",
    ]
    items = [
        (str(k).strip(), str(v).strip())
        for k, v in specs.items()
        if v not in (None, "") and len(str(v)) <= 60
    ]

    out = []
    for needle in priority:
        for k, v in items:
            if needle in k.lower() and (k, v) not in out:
                out.append((k, v))
                if len(out) >= limit:
                    return out

    for pair in items:
        if pair not in out:
            out.append(pair)
        if len(out) >= limit:
            break

    return out


def platform_tag(draw, x, y, label):
    label = str(label or "").title()
    if not label:
        return
    f = font(13, True)
    width = draw.textbbox((0, 0), label, font=f)[2] + 24
    fill = {
        "Amazon": (255, 247, 228),
        "Flipkart": (235, 245, 255),
        "Croma": (229, 255, 245),
    }.get(label, (237, 245, 255))
    draw.rounded_rectangle((x, y, x+width, y+28), radius=14, fill=fill)
    draw.text((x+12, y+6), label, font=f, fill=(39, 66, 112))


def price_badge(draw, x, y, width, value):
    draw.rounded_rectangle((x, y, x+width, y+52), radius=17, fill=YELLOW)
    f = fit(draw, value, width-18, 29, 20, True)
    draw.text((x+width/2, y+26), value, font=f, fill=INK, anchor="mm")


def draw_small(canvas, product, box, rank):
    x1, y1, x2, y2 = box
    draw = ImageDraw.Draw(canvas)

    # Card
    draw.rounded_rectangle((x1, y1, x2, y2), radius=28, fill=(250, 252, 255), outline=(217, 229, 242), width=2)

    # Rank badge
    draw.ellipse((x1+10, y1+10, x1+52, y1+52), fill=NAVY)
    draw.text((x1+31, y1+31), str(rank), font=font(17, True), fill=WHITE, anchor="mm")

    # Product image
    img_h = 170
    draw.rounded_rectangle((x1+16, y1+57, x2-16, y1+57+img_h), radius=23, fill=(245, 249, 253))
    img = load_image(product["image_url"], (x2-x1-32, img_h))
    canvas.alpha_composite(img, (x1+16, y1+57))
    draw = ImageDraw.Draw(canvas)

    # Product name
    title, tf = wrap(draw, product.get("full_title") or product.get("title"), x2-x1-32, 17, 12, 2)
    draw.multiline_text((x1+16, y1+238), title, font=tf, fill=INK, spacing=2)

    price_badge(draw, x1+16, y2-65, x2-x1-32, product.get("price_display") or money(product.get("price")))
    platform_tag(draw, x1+16, y2-31, product.get("platform"))


def draw_featured(canvas, product, box):
    x1, y1, x2, y2 = box
    draw = ImageDraw.Draw(canvas)

    # Glossy podium panel
    draw.rounded_rectangle((x1, y1, x2, y2), radius=34, fill=(26, 100, 218))
    draw.rounded_rectangle((x1+9, y1+9, x2-9, y2-9), radius=30, fill=(9, 57, 133))

    # Featured badge
    draw.ellipse((x1+25, y1-27, x1+83, y1+31), fill=YELLOW, outline=WHITE, width=3)
    draw.text((x1+54, y1+2), "#1", font=font(22, True), fill=INK, anchor="mm")

    draw.rounded_rectangle((x1+54, y1+23, x2-54, y1+59), radius=18, fill=WHITE)
    draw.text(((x1+x2)/2, y1+31), "FEATURED PICK", font=font(14, True), fill=PURPLE, anchor="ma")

    # Image
    img_h = 255
    draw.rounded_rectangle((x1+35, y1+72, x2-35, y1+72+img_h), radius=28, fill=(243, 248, 255))
    img = load_image(product["image_url"], (x2-x1-70, img_h))
    canvas.alpha_composite(img, (x1+35, y1+72))
    draw = ImageDraw.Draw(canvas)

    # Name + factual specs
    title, tf = wrap(draw, product.get("full_title") or product.get("title"), x2-x1-70, 20, 13, 2)
    draw.multiline_text(((x1+x2)/2, y1+344), title, font=tf, fill=WHITE, spacing=2, anchor="ma")

    pairs = product_specs(product, 3)
    if pairs:
        col = (x2-x1-70) / len(pairs)
        for i, (k, v) in enumerate(pairs):
            short = f"{k.title()}: {v}"
            if len(short) > 24:
                short = short[:23] + "…"
            draw.text((x1+35+i*col, y1+395), short, font=font(11, True), fill=(220, 235, 255))

    price_badge(draw, x1+42, y2-82, x2-x1-84, product.get("price_display") or money(product.get("price")))
    platform_tag(draw, x1+42, y2-38, product.get("platform"))


def render(ad):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ad_id = ad["ad_id"]
    out = OUT_DIR / f"{ad_id}_premium_1080x1350.png"

    canvas = Image.new("RGBA", (W, H), PALE + (255,))
    draw = ImageDraw.Draw(canvas)

    # APPROVED MASTER BACKGROUND
    draw.rectangle((0, 0, W, H), fill=(225, 242, 255))
    glow(canvas, 120, 215, 250, (80, 190, 255, 105))
    glow(canvas, 920, 225, 260, (145, 72, 255, 95))
    glow(canvas, 520, 730, 330, (255, 255, 255, 155))

    # Smooth white/blue waves
    draw.pieslice((-250, -180, 560, 560), 5, 170, fill=(255, 255, 255, 130))
    draw.pieslice((590, 170, 1300, 880), 170, 350, fill=(200, 228, 255, 150))
    draw.ellipse((-80, 860, 350, 1290), fill=(209, 241, 255, 120))

    # Bright accent shards
    for pts, fill in [
        ([(530, 62), (650, 18), (605, 98)], (255, 194, 34)),
        ([(675, 45), (810, 20), (742, 98)], (103, 44, 239)),
        ([(470, 142), (535, 94), (540, 170)], (245, 72, 184)),
        ([(835, 106), (925, 70), (900, 152)], (255, 203, 35)),
    ]:
        draw.polygon(pts, fill=fill)

    # Fixed header / branding
    try:
        logo = load_image(LOGO_URL, (108, 58))
        canvas.alpha_composite(logo, (44, 30))
    except Exception:
        pass
    draw = ImageDraw.Draw(canvas)
    draw.text((165, 32), "TrustFolio", font=font(40, True), fill=INK)
    draw.text((165, 79), "Compare • Save • Shop Smart", font=font(17), fill=MUTED)
    draw.text((1024, 38), "Smart", font=font(20, True), fill=PURPLE, anchor="ra")
    draw.text((1024, 66), "Shopping", font=font(20, True), fill=BLUE, anchor="ra")
    draw.text((1024, 94), "Smarter You", font=font(15, True), fill=INK, anchor="ra")

    # Headline block stays fixed; only data-driven words/budget change.
    headline = str(ad.get("headline") or "")
    left, budget = parse_budget(headline)
    draw.rounded_rectangle((420, 112, 1033, 230), radius=34, fill=(77, 22, 197), outline=(126, 57, 255), width=4)
    draw.rounded_rectangle((435, 124, 1018, 219), radius=27, fill=(55, 24, 127))
    hf = fit(draw, left, 535, 34, 23, True)
    draw.text((727, 153), left, font=hf, fill=WHITE, anchor="ma")
    if budget:
        bf = fit(draw, f"Under {budget}", 540, 54, 34, True)
        draw.text((727, 203), f"Under {budget}", font=bf, fill=YELLOW, anchor="ma")

    sub = "Top 5 Picks • Real Product Images • Live Prices"
    if ad.get("ad_type") == "price_comparison":
        sub = "Compare the same product across major platforms"
    draw.rounded_rectangle((402, 242, 1042, 288), radius=23, fill=YELLOW)
    draw.text((722, 265), sub, font=font(16, True), fill=INK, anchor="mm")

    # Left benefit stack
    benefits = [
        ("COMPARE PRICES", "Across Top Websites", BLUE),
        ("LATEST MODELS", "Real Price Data", (4, 174, 126)),
        ("TOP PICKS", "Selected from TrustFolio", PURPLE),
        ("BEST DEALS", "Within Your Budget", (27, 116, 232)),
    ]
    y = 122
    for title, subtitle, color in benefits:
        draw.rounded_rectangle((48, y, 350, y+58), radius=29, fill=(255, 255, 255, 235), outline=(210, 229, 246), width=2)
        draw.ellipse((58, y+8, 102, y+52), fill=color)
        draw.text((80, y+30), "✓", font=font(22, True), fill=WHITE, anchor="mm")
        draw.text((116, y+13), title, font=font(13, True), fill=INK)
        draw.text((116, y+33), subtitle, font=font(10), fill=MUTED)
        y += 66

    products = (ad.get("image_ad") or {}).get("products", [])[:5]
    if not products:
        raise RuntimeError(f"{ad_id}: no products in manifest")

    # LOCKED 5-product mapping matches the approved reference:
    # left = product 1, center = product 5, right = product 2,
    # bottom-left = product 3, bottom-right = product 4.
    if len(products) >= 5:
        left = products[0]
        center = products[4]
        right = products[1]
        bottom_left = products[2]
        bottom_right = products[3]

        # Main white stage
        draw.rounded_rectangle((37, 355, 1043, 1238), radius=42, fill=(255, 255, 255, 238), outline=(213, 229, 245), width=2)

        # Center featured podium
        draw_featured(canvas, center, (344, 404, 736, 948))
        draw_small(canvas, left, (62, 423, 322, 808), 2)
        draw_small(canvas, right, (758, 423, 1018, 808), 3)
        draw_small(canvas, bottom_left, (140, 850, 493, 1158), 4)
        draw_small(canvas, bottom_right, (588, 850, 941, 1158), 5)
    else:
        # Keep the same visual family for 1–4 product ads.
        draw.rounded_rectangle((37, 355, 1043, 1238), radius=42, fill=(255,255,255,238), outline=(213,229,245), width=2)
        if len(products) == 4:
            draw_small(canvas, products[0], (65, 425, 325, 810), 1)
            draw_small(canvas, products[1], (755, 425, 1015, 810), 2)
            draw_featured(canvas, products[2], (344, 408, 736, 948))
            draw_small(canvas, products[3], (363, 850, 717, 1158), 4)
        elif len(products) == 3:
            draw_small(canvas, products[0], (65, 475, 325, 850), 1)
            draw_featured(canvas, products[1], (344, 408, 736, 948))
            draw_small(canvas, products[2], (755, 475, 1015, 850), 3)
        elif len(products) == 2:
            draw_featured(canvas, products[0], (93, 425, 510, 980))
            draw_featured(canvas, products[1], (570, 425, 987, 980))
        else:
            draw_featured(canvas, products[0], (260, 430, 820, 1030))

    # Fixed bottom benefit strip
    draw.rounded_rectangle((48, 1172, 1032, 1233), radius=28, fill=NAVY)
    items = [
        ("₹", "Compare Prices"),
        ("✓", "Find Better Deals"),
        ("★", "Latest Products"),
        ("✓", "No Login"),
    ]
    xs = [103, 347, 591, 835]
    fills = [(246, 71, 183), (255, 195, 38), (0, 204, 176), PURPLE]
    for (icon, label), xx, fill in zip(items, xs, fills):
        draw.ellipse((xx-22, 1181, xx+22, 1225), fill=fill)
        draw.text((xx, 1203), icon, font=font(19, True), fill=WHITE, anchor="mm")
        draw.text((xx+38, 1189), label, font=font(12, True), fill=WHITE)
        draw.text((xx+38, 1208), "TrustFolio", font=font(9), fill=(191, 207, 232))

    # CTA + footer
    draw.rounded_rectangle((60, 1250, 670, 1319), radius=31, fill=YELLOW)
    draw.text((365, 1284), "Compare Now on TrustFolio  →", font=font(24, True), fill=INK, anchor="mm")
    draw.text((1018, 1264), "trustfolio.in", font=font(26, True), fill=NAVY, anchor="ra")
    draw.text((1018, 1297), "Smart Shopping for a Smarter You", font=font(11), fill=MUTED, anchor="ra")

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
