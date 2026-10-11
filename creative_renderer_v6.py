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
VERSION = "V6"
OUT_DIR = BASE / "ads" / "generated_creatives" / "feed"
LOGO_URL = "https://www.trustfolio.in/logo.png"

W, H = 1080, 1350

# Locked reference-style palette.
NAVY = (5, 23, 58)
NAVY_2 = (9, 48, 111)
BLUE = (31, 116, 241)
CYAN = (38, 207, 255)
PURPLE = (100, 33, 235)
PURPLE_DARK = (58, 18, 139)
PINK = (245, 68, 183)
YELLOW = (255, 218, 35)
WHITE = (255, 255, 255)
INK = (12, 27, 51)
MUTED = (84, 102, 129)
PALE = (226, 243, 255)
BORDER = (210, 228, 246)


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
    if not url:
        raise RuntimeError("Missing URL")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "TrustFolioCreativeRenderer/6.0"},
    )
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
            return "\n".join(lines), f

    f = font(minimum, True)
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


def parse_budget(headline):
    m = re.match(r"^(.*?)(?:\s+Under\s+)(₹[\d,]+)$", str(headline or ""), re.I)
    if not m:
        return str(headline or ""), None
    return m.group(1).strip(), m.group(2)


def glow(canvas, cx, cy, radius, rgba):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        fill=rgba,
    )
    layer = layer.filter(ImageFilter.GaussianBlur(max(10, radius // 3)))
    canvas.alpha_composite(layer)


def product_title(product):
    return product.get("full_title") or product.get("title") or ""


def product_specs(product, limit=3):
    specs = product.get("specifications") or {}
    if not isinstance(specs, dict):
        return []

    priority = [
        "display", "screen size", "size", "battery", "ram", "storage",
        "resolution", "connectivity", "processor", "refresh rate",
        "capacity", "power", "watt", "type",
    ]

    items = [
        (str(k).strip(), str(v).strip())
        for k, v in specs.items()
        if v not in (None, "") and len(str(v)) <= 60
    ]

    selected = []
    for needle in priority:
        for k, v in items:
            if needle in k.lower() and (k, v) not in selected:
                selected.append((k, v))
                if len(selected) >= limit:
                    return selected

    for pair in items:
        if pair not in selected:
            selected.append(pair)
        if len(selected) >= limit:
            break

    return selected


def platform_tag(draw, x, y, label):
    label = str(label or "").title()
    if not label:
        return

    f = font(12, True)
    width = draw.textbbox((0, 0), label, font=f)[2] + 24
    fill = {
        "Amazon": (255, 247, 228),
        "Flipkart": (235, 245, 255),
        "Croma": (228, 255, 244),
    }.get(label, (237, 245, 255))

    draw.rounded_rectangle(
        (x, y, x + width, y + 28),
        radius=14,
        fill=fill,
    )
    draw.text((x + 12, y + 7), label, font=f, fill=(35, 63, 106))


def price_badge(draw, x, y, width, price):
    draw.rounded_rectangle(
        (x, y, x + width, y + 52),
        radius=18,
        fill=YELLOW,
    )
    f = fit(draw, price, width - 16, 29, 20, True)
    draw.text(
        (x + width / 2, y + 26),
        price,
        font=f,
        fill=INK,
        anchor="mm",
    )


def small_card(canvas, product, box, rank):
    x1, y1, x2, y2 = box
    draw = ImageDraw.Draw(canvas)

    draw.rounded_rectangle(
        (x1, y1, x2, y2),
        radius=28,
        fill=(249, 252, 255),
        outline=(207, 224, 242),
        width=2,
    )

    # Rank circle
    draw.ellipse(
        (x1 + 10, y1 + 10, x1 + 53, y1 + 53),
        fill=NAVY,
    )
    draw.text(
        (x1 + 31.5, y1 + 31.5),
        str(rank),
        font=font(17, True),
        fill=WHITE,
        anchor="mm",
    )

    # Responsive product image: shorter cards get a shorter image slot so
    # product titles never collide with the price badge.
    card_h = y2 - y1
    img_h = min(155, int(card_h * 0.42))
    draw.rounded_rectangle(
        (x1 + 15, y1 + 58, x2 - 15, y1 + 58 + img_h),
        radius=22,
        fill=(245, 249, 254),
    )
    img = load_image(
        product.get("image_url", ""),
        (x2 - x1 - 30, img_h),
    )
    canvas.alpha_composite(img, (x1 + 15, y1 + 58))
    draw = ImageDraw.Draw(canvas)

    title, tf = wrap(
        draw,
        product_title(product),
        x2 - x1 - 30,
        start=16,
        minimum=10,
        max_lines=2,
    )

    title_y = y1 + 58 + img_h + 8
    draw.multiline_text(
        (x1 + 15, title_y),
        title,
        font=tf,
        fill=INK,
        spacing=2,
    )

    price_badge(
        draw,
        x1 + 15,
        y2 - 64,
        x2 - x1 - 30,
        product.get("price_display") or money(product.get("price")),
    )
    platform_tag(draw, x1 + 15, y2 - 31, product.get("platform"))


def podium_featured(canvas, product, box):
    x1, y1, x2, y2 = box
    draw = ImageDraw.Draw(canvas)
    box_h = y2 - y1

    # Outer glow and a compact podium that scales to the available stage.
    glow(canvas, (x1 + x2) // 2, y2 - 20, 110, (52, 177, 255, 65))
    draw.rounded_rectangle(
        (x1, y1, x2, y2),
        radius=30,
        fill=(24, 108, 224),
    )
    draw.rounded_rectangle(
        (x1 + 9, y1 + 9, x2 - 9, y2 - 9),
        radius=27,
        fill=(7, 57, 135),
    )

    # Low-profile 3D podium lip, kept behind all text and price elements.
    cap_y = y1 + int(box_h * 0.70)
    draw.ellipse(
        (x1 + 4, cap_y, x2 - 4, min(y2 - 8, cap_y + 46)),
        fill=(16, 79, 171),
        outline=(70, 201, 255),
        width=3,
    )
    draw.rectangle(
        (x1 + 4, cap_y + 22, x2 - 4, y2 - 12),
        fill=(9, 57, 135),
    )

    # #1 badge and featured ribbon.
    draw.ellipse(
        (x1 + 19, y1 - 31, x1 + 80, y1 + 30),
        fill=YELLOW,
        outline=WHITE,
        width=3,
    )
    draw.text(
        (x1 + 49.5, y1),
        "#1",
        font=font(22, True),
        fill=INK,
        anchor="mm",
    )
    draw.rounded_rectangle(
        (x1 + 53, y1 + 18, x2 - 53, y1 + 56),
        radius=19,
        fill=WHITE,
    )
    draw.text(
        ((x1 + x2) / 2, y1 + 27),
        "FEATURED PICK",
        font=font(14, True),
        fill=PURPLE,
        anchor="ma",
    )

    # Responsive image panel.
    img_h = min(230, max(150, int(box_h * 0.42)))
    img_y = y1 + 67
    draw.rounded_rectangle(
        (x1 + 38, img_y, x2 - 38, img_y + img_h),
        radius=26,
        fill=(244, 248, 253),
    )
    img = load_image(
        product.get("image_url", ""),
        (x2 - x1 - 76, img_h),
    )
    canvas.alpha_composite(
        img,
        (x1 + 38 + (x2 - x1 - 76 - img.width) // 2, img_y),
    )
    draw = ImageDraw.Draw(canvas)

    title, tf = wrap(
        draw,
        product_title(product),
        x2 - x1 - 76,
        start=17,
        minimum=12,
        max_lines=2,
    )
    title_y = img_y + img_h + 7
    draw.multiline_text(
        ((x1 + x2) / 2, title_y),
        title,
        font=tf,
        fill=WHITE,
        spacing=2,
        anchor="ma",
        align="center",
    )

    # Compact spec line; keep it clear of the price area.
    specs = product_specs(product, 2)
    spec_y = title_y + 43
    if specs and spec_y < y2 - 105:
        col = (x2 - x1 - 70) / len(specs)
        for i, (k, v) in enumerate(specs):
            text = f"{k.title()}: {v}"
            if len(text) > 22:
                text = text[:21] + "…"
            draw.text(
                (x1 + 35 + i * col, spec_y),
                text,
                font=font(9, True),
                fill=(215, 232, 255),
            )

    # Lift the price above the podium base and keep retailer label below it.
    price_badge(
        draw,
        x1 + 45,
        y2 - 91,
        x2 - x1 - 90,
        product.get("price_display") or money(product.get("price")),
    )
    platform_tag(
        draw,
        x1 + 45,
        y2 - 31,
        product.get("platform"),
    )

def draw_benefits(draw):
    items = [
        ("COMPARE PRICES", "Across Top Websites", BLUE),
        ("LATEST MODELS", "Real Price Data", (3, 177, 129)),
        ("TOP PICKS", "Selected from TrustFolio", PURPLE),
        ("BEST DEALS", "Within Your Budget", (31, 116, 232)),
    ]

    y = 125
    for title, subtitle, color in items:
        draw.rounded_rectangle(
            (48, y, 350, y + 55),
            radius=27,
            fill=(255, 255, 255, 238),
            outline=(207, 226, 245),
            width=2,
        )
        draw.ellipse((59, y + 8, 102, y + 51), fill=color)
        draw.text(
            (80.5, y + 29.5),
            "✓",
            font=font(20, True),
            fill=WHITE,
            anchor="mm",
        )
        draw.text(
            (116, y + 12),
            title,
            font=font(12, True),
            fill=INK,
        )
        draw.text(
            (116, y + 32),
            subtitle,
            font=font(9),
            fill=MUTED,
        )
        y += 63


def draw_bottom_bar(draw):
    draw.rounded_rectangle(
        (48, 1176, 1032, 1234),
        radius=29,
        fill=NAVY,
    )

    items = [
        ("₹", "Compare Prices"),
        ("✓", "Find Better Deals"),
        ("★", "Latest Products"),
        ("✓", "No Login"),
    ]
    xs = [102, 347, 592, 837]
    colors = [PINK, YELLOW, CYAN, PURPLE]

    for (icon, label), xx, color in zip(items, xs, colors):
        draw.ellipse(
            (xx - 21, 1184, xx + 21, 1226),
            fill=color,
        )
        draw.text(
            (xx, 1205),
            icon,
            font=font(18, True),
            fill=WHITE if color != YELLOW else INK,
            anchor="mm",
        )
        draw.text(
            (xx + 37, 1192),
            label,
            font=font(11, True),
            fill=WHITE,
        )
        draw.text(
            (xx + 37, 1210),
            "TrustFolio",
            font=font(8),
            fill=(185, 204, 234),
        )


def render(ad):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ad_id = ad["ad_id"]
    out = OUT_DIR / f"{ad_id}_premium_1080x1350.png"

    canvas = Image.new("RGBA", (W, H), PALE + (255,))
    draw = ImageDraw.Draw(canvas)

    # Reference-style luminous background.
    draw.rectangle((0, 0, W, H), fill=(226, 243, 255))
    glow(canvas, 110, 190, 270, (85, 193, 255, 110))
    glow(canvas, 910, 215, 280, (143, 77, 250, 95))
    glow(canvas, 520, 730, 340, (255, 255, 255, 165))
    glow(canvas, 900, 1070, 190, (52, 220, 255, 75))

    draw.pieslice((-260, -210, 620, 545), 5, 170, fill=(255, 255, 255, 140))
    draw.pieslice((590, 195, 1290, 900), 174, 350, fill=(204, 230, 255, 155))
    draw.ellipse((-90, 870, 350, 1290), fill=(205, 240, 255, 125))

    for pts, fill in [
        ([(530, 62), (655, 16), (606, 102)], (255, 193, 31)),
        ([(680, 42), (811, 18), (744, 99)], (103, 45, 239)),
        ([(472, 142), (540, 91), (543, 171)], (246, 71, 181)),
        ([(840, 106), (927, 71), (900, 150)], (255, 203, 32)),
    ]:
        draw.polygon(pts, fill=fill)

    # Fixed TrustFolio header.
    try:
        logo = load_image(LOGO_URL, (106, 57))
        canvas.alpha_composite(logo, (43, 27))
    except Exception:
        pass

    draw = ImageDraw.Draw(canvas)
    draw.text((162, 29), "TrustFolio", font=font(40, True), fill=INK)
    draw.text((162, 76), "Compare • Save • Shop Smart", font=font(17), fill=MUTED)

    draw.text((1022, 35), "Smart", font=font(19, True), fill=PURPLE, anchor="ra")
    draw.text((1022, 61), "Shopping", font=font(19, True), fill=BLUE, anchor="ra")
    draw.text((1022, 88), "Smarter You", font=font(14, True), fill=INK, anchor="ra")

    # Left benefits sit entirely above the product stage.
    draw_benefits(draw)

    # Hero title area.
    headline = str(ad.get("headline") or "")
    left, budget = parse_budget(headline)

    # Purple title panel.
    draw.rounded_rectangle(
        (416, 110, 1037, 207),
        radius=34,
        fill=(93, 30, 219),
        outline=(128, 65, 255),
        width=4,
    )
    draw.rounded_rectangle(
        (430, 122, 1023, 196),
        radius=26,
        fill=(53, 23, 119),
    )

    hf = fit(draw, left, 540, 31, 20, True)
    draw.text(
        (726, 158),
        left,
        font=hf,
        fill=WHITE,
        anchor="mm",
    )

    # Separate budget line prevents the overlap seen in V5.
    if budget:
        bf = fit(draw, f"Under {budget}", 520, 43, 28, True)
        draw.text(
            (724, 220),
            f"Under {budget}",
            font=bf,
            fill=YELLOW,
            anchor="mm",
        )
    else:
        bf = fit(draw, headline, 560, 38, 24, True)
        draw.text(
            (724, 220),
            headline,
            font=bf,
            fill=YELLOW,
            anchor="mm",
        )

    subtitle = (
        "Top 5 Picks • Real Product Images • Live Prices"
        if ad.get("ad_type") != "price_comparison"
        else "Compare the same product across major platforms"
    )

    draw.rounded_rectangle(
        (416, 258, 1037, 302),
        radius=22,
        fill=YELLOW,
    )
    draw.text(
        (726, 280),
        subtitle,
        font=font(15, True),
        fill=INK,
        anchor="mm",
    )

    # Main white stage. Starts below the benefits to eliminate clipping.
    draw.rounded_rectangle(
        (36, 390, 1044, 1239),
        radius=40,
        fill=(255, 255, 255, 238),
        outline=BORDER,
        width=2,
    )

    products = (ad.get("image_ad") or {}).get("products", [])[:5]
    if not products:
        raise RuntimeError(f"{ad_id}: no products in manifest")

    # Locked 5-product reference mapping.
    if len(products) >= 5:
        left = products[0]
        center = products[4]
        right = products[1]
        bottom_left = products[2]
        bottom_right = products[3]

        small_card(canvas, left, (62, 445, 323, 805), 2)
        small_card(canvas, right, (757, 445, 1018, 805), 3)
        podium_featured(canvas, center, (344, 421, 736, 840))
        small_card(canvas, bottom_left, (137, 848, 493, 1155), 4)
        small_card(canvas, bottom_right, (587, 848, 943, 1155), 5)
    else:
        # Variable-count fallback keeps the same visual family.
        if len(products) == 4:
            small_card(canvas, products[0], (62, 450, 323, 805), 1)
            small_card(canvas, products[1], (757, 450, 1018, 805), 2)
            podium_featured(canvas, products[2], (344, 421, 736, 940))
            small_card(canvas, products[3], (350, 850, 730, 1155), 4)
        elif len(products) == 3:
            small_card(canvas, products[0], (62, 490, 323, 850), 1)
            podium_featured(canvas, products[1], (344, 421, 736, 940))
            small_card(canvas, products[2], (757, 490, 1018, 850), 3)
        elif len(products) == 2:
            podium_featured(canvas, products[0], (86, 445, 505, 995))
            podium_featured(canvas, products[1], (575, 445, 994, 995))
        else:
            podium_featured(canvas, products[0], (260, 445, 820, 1045))

    draw = ImageDraw.Draw(canvas)
    draw_bottom_bar(draw)

    # CTA/footer fixed.
    draw.rounded_rectangle(
        (59, 1250, 666, 1318),
        radius=32,
        fill=YELLOW,
    )
    draw.text(
        (362, 1284),
        "Compare Now on TrustFolio  →",
        font=font(24, True),
        fill=INK,
        anchor="mm",
    )
    draw.text(
        (1020, 1263),
        "trustfolio.in",
        font=font(26, True),
        fill=NAVY,
        anchor="ra",
    )
    draw.text(
        (1020, 1296),
        "Smart Shopping for a Smarter You",
        font=font(11),
        fill=MUTED,
        anchor="ra",
    )

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
