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
OUT_DIR = BASE / "ads" / "generated_creatives" / "feed"
LOGO_URL = "https://www.trustfolio.in/logo.png"

W, H = 1080, 1350
NAVY = (12, 24, 52)
DEEP = (23, 30, 75)
BLUE = (39, 110, 229)
CYAN = (70, 194, 255)
PURPLE = (116, 53, 242)
PINK = (244, 79, 180)
YELLOW = (255, 214, 47)
WHITE = (255, 255, 255)
TEXT = (23, 31, 50)
MUTED = (91, 105, 127)
PALE = (246, 249, 255)
LINE = (220, 228, 241)


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
        url,
        headers={"User-Agent": "TrustFolioCreativeRenderer/3.0"},
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def load_image(url, box):
    raw = get_bytes(url)
    src = Image.open(io.BytesIO(raw)).convert("RGBA")
    src.thumbnail(box, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", box, (255, 255, 255, 0))
    canvas.alpha_composite(
        src,
        ((box[0] - src.width) // 2, (box[1] - src.height) // 2),
    )
    return canvas


def fit_text(draw, text, width, start, minimum=16, bold=True):
    size = start
    while size >= minimum:
        f = font(size, bold)
        if draw.textbbox((0, 0), str(text), font=f)[2] <= width:
            return f
        size -= 1
    return font(minimum, bold)


def wrap(draw, text, width, start=19, minimum=14, max_lines=2):
    words = " ".join(str(text or "").split()).split()
    if not words:
        return "", font(minimum, True)

    f = fit_text(draw, " ".join(words), width, start, minimum, True)
    lines, current = [], ""
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

    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while (
            draw.textbbox((0, 0), last + "…", font=f)[2] > width
            and len(last) > 5
        ):
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"

    return "\n".join(lines), f


def format_inr(value):
    if value in (None, ""):
        return ""
    try:
        n = float(value)
        return f"₹{int(n):,}" if n.is_integer() else f"₹{n:,.0f}"
    except (TypeError, ValueError):
        return str(value)


def gradient(canvas, box, c1, c2):
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pix = layer.load()
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        for x in range(w):
            pix[x, y] = (r, g, b, 255)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, w - 1, h - 1), radius=34, fill=255)
    canvas.alpha_composite(
        Image.composite(layer, Image.new("RGBA", (w, h)), mask),
        (x1, y1),
    )


def glow(canvas, cx, cy, radius, rgba):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        fill=rgba,
    )
    layer = layer.filter(ImageFilter.GaussianBlur(max(14, radius // 2)))
    canvas.alpha_composite(layer)


def specs_for(product, max_items=2):
    specs = product.get("specifications") or {}
    if not isinstance(specs, dict):
        return []

    priority = [
        "display", "screen size", "size", "battery", "ram", "storage",
        "rom", "capacity", "power", "watt", "resolution", "connectivity",
        "processor", "refresh rate", "type", "star rating",
    ]

    pairs = []
    normalized = [(str(k).strip(), str(v).strip()) for k, v in specs.items() if v not in (None, "")]
    normalized = [(k, v) for k, v in normalized if len(v) <= 70]

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


def platform_pill(draw, x, y, label):
    label = str(label or "").title()
    if not label:
        return
    f = font(14, True)
    tw = draw.textbbox((0, 0), label, font=f)[2] + 26
    draw.rounded_rectangle(
        (x, y, x + tw, y + 30),
        radius=15,
        fill=(236, 244, 255),
    )
    draw.text((x + 13, y + 7), label, font=f, fill=(34, 76, 138))


def price_box(draw, x, y, w, price):
    draw.rounded_rectangle(
        (x, y, x + w, y + 54),
        radius=18,
        fill=YELLOW,
    )
    pf = fit_text(draw, str(price), w - 24, 30, 22, True)
    draw.text((x + w / 2, y + 27), str(price), font=pf, fill=(19, 27, 45), anchor="mm")


def draw_product_chip(canvas, draw, product, box, number=None, featured=False):
    x1, y1, x2, y2 = box
    gradient(
        canvas,
        box,
        (255, 255, 255, 255),
        (244, 248, 255, 255),
    )
    draw = ImageDraw.Draw(canvas)

    if number is not None:
        draw.ellipse(
            (x1 + 16, y1 + 16, x1 + 52, y1 + 52),
            fill=NAVY,
        )
        draw.text(
            (x1 + 34, y1 + 34),
            str(number),
            font=font(15, True),
            fill=WHITE,
            anchor="mm",
        )

    img_h = int((y2 - y1) * (0.57 if featured else 0.51))
    img_box = (x2 - x1 - 30, img_h)
    draw.rounded_rectangle(
        (x1 + 15, y1 + 58, x2 - 15, y1 + 58 + img_h),
        radius=24,
        fill=(250, 251, 254),
    )
    pimg = load_image(product.get("image_url", ""), img_box)
    canvas.alpha_composite(
        pimg,
        (x1 + (x2 - x1 - pimg.width) // 2, y1 + 58),
    )
    draw = ImageDraw.Draw(canvas)

    title, tf = wrap(
        draw,
        product.get("full_title") or product.get("title", ""),
        x2 - x1 - 34,
        start=22 if featured else 18,
        minimum=15 if featured else 13,
        max_lines=2,
    )

    title_y = y1 + 58 + img_h + 15
    draw.multiline_text(
        (x1 + 17, title_y),
        title,
        font=tf,
        fill=TEXT,
        spacing=3,
    )

    rating = product.get("rating")
    if rating not in (None, ""):
        try:
            rating_text = f"★ {float(rating):.1f}"
            draw.text(
                (x2 - 18, title_y + 3),
                rating_text,
                font=font(14, True),
                fill=(218, 139, 0),
                anchor="ra",
            )
        except (TypeError, ValueError):
            pass

    price = product.get("price_display") or format_inr(product.get("price"))
    price_y = y2 - 78 if featured else y2 - 69
    price_box(draw, x1 + 16, price_y, x2 - x1 - 32, price)

    platform = product.get("platform")
    platform_pill(draw, x1 + 16, y2 - 45, platform)

    if featured:
        pairs = specs_for(product, 2)
        sx = x1 + 18
        sy = y2 - 142
        for key, value in pairs:
            short = f"{key.title()}: {value}"
            if len(short) > 32:
                short = short[:31] + "…"
            draw.text(
                (sx, sy),
                short,
                font=font(13, True),
                fill=MUTED,
            )
            sy += 21


def parse_headline(draw, headline):
    m = re.match(r"^(.*?)(?:\s+Under\s+)(₹[\d,]+)$", str(headline))
    if not m:
        return headline, None

    left = m.group(1).strip()
    budget = m.group(2)
    return left, budget


def render(ad):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ad_id = ad["ad_id"]
    out = OUT_DIR / f"{ad_id}_premium_1080x1350.png"

    canvas = Image.new("RGBA", (W, H), PALE + (255,))
    draw = ImageDraw.Draw(canvas)

    # Dynamic premium hero background
    draw.rectangle((0, 0, W, 450), fill=NAVY)
    glow(canvas, 890, 90, 190, (86, 184, 255, 90))
    glow(canvas, 200, 290, 150, (111, 78, 255, 70))
    glow(canvas, 740, 310, 120, (250, 80, 190, 55))

    # Decorative dynamic strokes/shapes
    draw.polygon(
        [(560, 15), (1010, 0), (950, 84), (680, 100)],
        fill=(84, 175, 255, 100),
    )
    draw.polygon(
        [(480, 112), (990, 44), (920, 125), (590, 170)],
        fill=(140, 66, 240, 110),
    )
    draw.ellipse((905, 20, 950, 65), fill=(255, 205, 64, 190))
    draw.ellipse((964, 135, 992, 163), fill=(70, 205, 255, 220))

    # Logo
    try:
        logo = load_image(LOGO_URL, (155, 72))
        canvas.alpha_composite(logo, (55, 34))
        draw = ImageDraw.Draw(canvas)
    except Exception:
        draw.text((58, 42), "TrustFolio", font=font(35, True), fill=WHITE)

    draw.text(
        (55, 111),
        "Compare • Save • Shop Smart",
        font=font(18, True),
        fill=(216, 231, 250),
    )
    draw.text(
        (1025, 56),
        "SMART SHOPPING",
        font=font(14, True),
        fill=(175, 208, 244),
        anchor="ra",
    )

    headline = str(ad.get("headline") or "")
    left, budget = parse_headline(draw, headline)
    hf = fit_text(draw, left, 930, 40, 27, True)
    draw.text((55, 155), left, font=hf, fill=WHITE)

    if budget:
        bf = fit_text(draw, budget, 500, 64, 42, True)
        draw.text((55, 205), f"UNDER {budget}", font=bf, fill=YELLOW)

    ad_type = ad.get("ad_type", "")
    if ad_type == "price_comparison":
        saving = ad.get("saving_inr")
        if saving not in (None, ""):
            sub = f"Compare prices • Potential listed-price difference {format_inr(saving)}"
        else:
            sub = "Compare the same product across platforms"
    else:
        sub = "5 selected picks • Exact prices from TrustFolio data"

    sf = fit_text(draw, sub, 930, 18, 14, True)
    draw.text((55, 290), sub, font=sf, fill=(236, 241, 249))

    # Trust / data pills
    pills = ["LIVE PRODUCT DATA", "REAL PRICES", "TRUSTFOLIO PICKS"]
    x = 55
    for label in pills:
        tw = draw.textbbox((0, 0), label, font=font(13, True))[2] + 28
        draw.rounded_rectangle(
            (x, 330, x + tw, 368),
            radius=19,
            fill=(255, 255, 255),
        )
        draw.text((x + 14, 341), label, font=font(13, True), fill=(25, 53, 93))
        x += tw + 10

    # Main white stage
    draw.rounded_rectangle(
        (34, 395, W - 34, 1295),
        radius=40,
        fill=WHITE,
        outline=LINE,
        width=2,
    )

    products = (ad.get("image_ad") or {}).get("products", [])[:5]
    if not products:
        raise RuntimeError(f"{ad_id}: no products in manifest")

    # Center feature + side pillars + two bottom cards
    draw_product_chip(
        canvas,
        draw,
        products[0],
        (342, 430, 738, 865),
        number=1,
        featured=True,
    )
    draw_product_chip(
        canvas,
        draw,
        products[1],
        (70, 475, 322, 820),
        number=2,
        featured=False,
    )
    draw_product_chip(
        canvas,
        draw,
        products[2],
        (758, 475, 1010, 820),
        number=3,
        featured=False,
    )
    draw_product_chip(
        canvas,
        draw,
        products[3],
        (135, 850, 505, 1135),
        number=4,
        featured=False,
    )
    draw_product_chip(
        canvas,
        draw,
        products[4],
        (575, 850, 945, 1135),
        number=5,
        featured=False,
    )

    # Featured ribbon
    draw.rounded_rectangle(
        (415, 412, 665, 450),
        radius=19,
        fill=PURPLE,
    )
    draw.text(
        (540, 421),
        "FEATURED PICK",
        font=font(15, True),
        fill=WHITE,
        anchor="ma",
    )

    # CTA
    draw.rounded_rectangle(
        (70, 1160, W - 70, 1248),
        radius=30,
        fill=NAVY,
    )
    draw.text(
        (99, 1184),
        "Compare before you buy",
        font=font(27, True),
        fill=WHITE,
    )
    draw.rounded_rectangle(
        (645, 1173, 990, 1235),
        radius=31,
        fill=YELLOW,
    )
    draw.text(
        (817, 1204),
        "Compare on TrustFolio →",
        font=font(20, True),
        fill=(17, 26, 44),
        anchor="mm",
    )

    # Footer
    draw.text(
        (55, 1270),
        "trustfolio.in",
        font=font(22, True),
        fill=BLUE,
    )
    draw.text(
        (1025, 1274),
        "Prices can change • Verify before checkout",
        font=font(13),
        fill=MUTED,
        anchor="ra",
    )

    final = Image.new("RGB", canvas.size, WHITE)
    final.paste(canvas, mask=canvas.getchannel("A"))
    final.save(out, quality=96, optimize=True)

    print("=" * 80)
    print("TRUSTFOLIO CREATIVE RENDERER V3")
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

    if ad_id:
        ad = next((x for x in ads if x.get("ad_id") == ad_id), None)
    else:
        ad = ads[0]

    if not ad:
        raise SystemExit(f"Ad ID not found: {ad_id}")

    render(ad)


if __name__ == "__main__":
    main()
