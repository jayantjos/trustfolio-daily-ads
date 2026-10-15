#!/usr/bin/env python3
"""TrustFolio V12 Universal Premium Renderer.

Permanent layout contract:
- assets/trustfolio_master_universal_v12.png is the frozen visual master.
- Layout/colors/rank positions/footer never change between categories.
- Only category, budget, product image, product name, price, retailer and 4 specs change.
- Text never shrinks to microscopic sizes: wrap/truncate rules preserve visual consistency.
- Product photos are white-background cut out, tightly cropped, and normalized to each visual slot.
"""

import json
import re
import sys
import importlib.util
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ADS = Path(__file__).resolve().parent
MASTER = ADS / "assets/trustfolio_master_universal_v12.png"
SOURCE = ADS / "master_template_renderer_final_v5.py"
OUT = ADS / "generated_creatives/feed"

spec = importlib.util.spec_from_file_location("tf_v5", SOURCE)
v5 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v5)

WHITE = (255, 255, 255)
INK = (7, 25, 57)
YELLOW = (255, 211, 20)
TOP_SPEC = (255, 255, 255)
BOTTOM_SPEC = (12, 31, 67)

# Canonical 20-category vocabulary used by TrustFolio.
CATEGORY_PROFILES = {
    "air-conditioner": {
        "label": "Air Conditioners",
        "aliases": ["air conditioner", "air conditioners", "ac"],
        "priority": ["ton", "star", "inverter", "warranty", "energy", "cooling"],
        "tagline": "Top 5 Picks for Cooling, Efficiency & Value",
    },
    "ceiling-fans": {
        "label": "Ceiling Fans",
        "aliases": ["ceiling fan", "ceiling fans", "fan"],
        "priority": ["sweep", "rpm", "speed", "watt", "power", "remote", "air delivery"],
        "tagline": "Top 5 Picks for Airflow, Efficiency & Value",
    },
    "cooler": {
        "label": "Air Coolers",
        "aliases": ["air cooler", "air coolers", "cooler", "coolers"],
        "priority": ["tank", "litre", "liter", "air delivery", "coverage", "watt", "power"],
        "tagline": "Top 5 Picks for Cooling, Coverage & Value",
    },
    "desktop-computers": {
        "label": "Desktop Computers",
        "aliases": ["desktop computer", "desktop computers", "desktop", "pc"],
        "priority": ["processor", "cpu", "ram", "memory", "ssd", "storage", "graphics", "gpu"],
        "tagline": "Top 5 Picks for Speed, Storage & Value",
    },
    "drones": {
        "label": "Drones",
        "aliases": ["drone", "drones"],
        "priority": ["camera", "flight", "range", "battery", "gps", "video"],
        "tagline": "Top 5 Picks for Camera, Flight & Value",
    },
    "fridge-refrigeration": {
        "label": "Refrigerators",
        "aliases": ["fridge", "refrigerator", "refrigerators", "refrigeration"],
        "priority": ["litre", "liter", "capacity", "star", "inverter", "frost", "energy"],
        "tagline": "Top 5 Picks for Storage, Efficiency & Value",
    },
    "geyser-water-heater": {
        "label": "Geysers",
        "aliases": ["geyser", "geysers", "water heater", "water heaters"],
        "priority": ["litre", "liter", "capacity", "watt", "power", "bar", "pressure", "warranty"],
        "tagline": "Top 5 Picks for Heating, Safety & Value",
    },
    "headphones-earbuds": {
        "label": "Headphones & Earbuds",
        "aliases": ["headphones earbuds", "headphone", "headphones", "earbud", "earbuds", "tws"],
        "priority": ["driver", "battery", "playtime", "anc", "noise", "bluetooth", "latency"],
        "tagline": "Top 5 Picks for Sound, Battery & Value",
    },
    "induction-cooktop": {
        "label": "Induction Cooktops",
        "aliases": ["induction cooktop", "induction cooktops", "induction"],
        "priority": ["watt", "power", "preset", "timer", "temperature", "warranty"],
        "tagline": "Top 5 Picks for Power, Control & Value",
    },
    "laptop": {
        "label": "Laptops",
        "aliases": ["laptop", "laptops", "notebook"],
        "priority": ["processor", "cpu", "ram", "memory", "ssd", "storage", "display", "graphics"],
        "tagline": "Top 5 Picks for Work, Speed & Value",
    },
    "microwave-oven": {
        "label": "Microwave Ovens",
        "aliases": ["microwave oven", "microwave ovens", "microwave"],
        "priority": ["litre", "liter", "capacity", "watt", "convection", "grill", "warranty"],
        "tagline": "Top 5 Picks for Cooking, Capacity & Value",
    },
    "mixer-grinder": {
        "label": "Mixer Grinders",
        "aliases": ["mixer grinder", "mixer grinders", "mixer", "grinder"],
        "priority": ["watt", "power", "jar", "jars", "rpm", "speed", "warranty"],
        "tagline": "Top 5 Picks for Power, Jars & Value",
    },
    "smart-phones": {
        "label": "Smartphones",
        "aliases": ["smart phone", "smart phones", "smartphone", "smartphones", "mobile", "mobiles"],
        "priority": ["display", "processor", "camera", "battery", "ram", "storage", "5g"],
        "tagline": "Top 5 Picks for Camera, Speed & Value",
    },
    "smart-tvs": {
        "label": "Smart TVs",
        "aliases": ["smart tv", "smart tvs", "television", "tv"],
        "priority": ["display", "inch", "resolution", "4k", "os", "sound", "watt"],
        "tagline": "Top 5 Picks for Picture, Sound & Value",
    },
    "smartwatches": {
        "label": "Smartwatches",
        "aliases": ["smartwatch", "smartwatches", "smart watch", "smart watches"],
        "priority": ["display", "calling", "bluetooth", "battery", "health", "spo2", "heart", "water", "ip"],
        "tagline": "Top 5 Picks for Style, Fitness & Value",
    },
    "speakers": {
        "label": "Speakers",
        "aliases": ["speaker", "speakers", "bluetooth speaker", "bluetooth speakers"],
        "priority": ["watt", "power", "battery", "bluetooth", "driver", "bass", "playtime"],
        "tagline": "Top 5 Picks for Sound, Bass & Value",
    },
    "tablets": {
        "label": "Tablets",
        "aliases": ["tablet", "tablets"],
        "priority": ["display", "processor", "ram", "storage", "battery", "camera"],
        "tagline": "Top 5 Picks for Display, Speed & Value",
    },
    "vacuum-cleaner": {
        "label": "Vacuum Cleaners",
        "aliases": ["vacuum cleaner", "vacuum cleaners", "vacuum"],
        "priority": ["suction", "pa", "watt", "power", "capacity", "filter", "hepa"],
        "tagline": "Top 5 Picks for Suction, Cleaning & Value",
    },
    "washing-machine": {
        "label": "Washing Machines",
        "aliases": ["washing machine", "washing machines", "washer"],
        "priority": ["kg", "capacity", "front", "top", "rpm", "star", "inverter"],
        "tagline": "Top 5 Picks for Cleaning, Efficiency & Value",
    },
    "water-purifier": {
        "label": "Water Purifiers",
        "aliases": ["water purifier", "water purifiers", "purifier", "ro purifier"],
        "priority": ["ro", "uv", "uf", "tds", "litre", "liter", "storage", "stage", "filter"],
        "tagline": "Top 5 Picks for Purity, Storage & Value",
    },
}

# Frozen pixel geometry for the approved 1024x1536 visual master.
SLOTS = {
    1: {
        "image": (391, 425, 646, 693),
        "name": (359, 777, 660, 831),
        "price": (389, 840, 635, 895),
        "merchant": (405, 903, 620, 934),
        "spec_centers": [(395, 972), (472, 972), (550, 972), (628, 972)],
        "spec_labels": [(356, 994, 434, 1038), (434, 994, 511, 1038), (511, 994, 589, 1038), (589, 994, 668, 1038)],
        "top": True,
    },
    2: {
        "image": (87, 454, 314, 687),
        "name": (77, 705, 320, 753),
        "price": (97, 762, 299, 806),
        "merchant": (105, 815, 291, 844),
        "spec_centers": [(103, 879), (165, 879), (227, 879), (289, 879)],
        "spec_labels": [(75, 900, 132, 939), (137, 900, 194, 939), (199, 900, 256, 939), (261, 900, 318, 939)],
        "top": True,
    },
    3: {
        "image": (711, 466, 941, 688),
        "name": (708, 705, 947, 753),
        "price": (726, 762, 925, 806),
        "merchant": (733, 815, 917, 844),
        "spec_centers": [(739, 879), (801, 879), (863, 879), (925, 879)],
        "spec_labels": [(710, 900, 768, 939), (772, 900, 830, 939), (834, 900, 892, 939), (896, 900, 954, 939)],
        "top": True,
    },
    4: {
        "image": (50, 997, 219, 1204),
        "name": (234, 1075, 426, 1112),
        "price": (242, 1115, 408, 1152),
        "merchant": (249, 1155, 393, 1182),
        "spec_centers": [(250, 1213), (301, 1213), (352, 1213), (403, 1213)],
        "spec_labels": [(228, 1233, 273, 1268), (279, 1233, 324, 1268), (330, 1233, 375, 1268), (381, 1233, 426, 1268)],
        "top": False,
    },
    5: {
        "image": (805, 997, 971, 1204),
        "name": (594, 1075, 784, 1112),
        "price": (607, 1115, 772, 1152),
        "merchant": (624, 1155, 759, 1182),
        "spec_centers": [(617, 1213), (668, 1213), (719, 1213), (770, 1213)],
        "spec_labels": [(595, 1233, 640, 1268), (646, 1233, 691, 1268), (697, 1233, 742, 1268), (748, 1233, 793, 1268)],
        "top": False,
    },
}


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def detect_category(ad):
    meta = ad.get("metadata") or {}
    candidates = [
        ad.get("category"), ad.get("category_name"), ad.get("category_slug"),
        meta.get("category"), meta.get("category_name"), meta.get("category_slug"),
        meta.get("campaign_title"), ad.get("title"),
    ]
    haystack = " | ".join(str(x) for x in candidates if x)
    nh = _norm(haystack)
    # longest aliases first avoids 'fan' beating 'ceiling fan', 'tv' beating 'smart tv'.
    ranked = []
    for key, profile in CATEGORY_PROFILES.items():
        for alias in profile["aliases"]:
            ranked.append((len(_norm(alias)), key, alias))
    for _, key, alias in sorted(ranked, reverse=True):
        if _norm(alias) in nh:
            return key, CATEGORY_PROFILES[key]
    # Fallback: derive a presentable label from campaign title.
    title = str(meta.get("campaign_title") or ad.get("title") or "Products")
    m = re.search(r"best\s+(.+?)(?:\s+under\s+|$)", title, re.I)
    label = (m.group(1) if m else title).strip(" -|") or "Products"
    return "generic", {
        "label": label,
        "priority": [],
        "tagline": "Top 5 Picks for Features, Performance & Value",
    }


def _money_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(round(float(value)))
    s = str(value).replace(",", "")
    m = re.search(r"(?:₹|rs\.?|inr)?\s*([0-9]+(?:\.[0-9]+)?)", s, re.I)
    return int(float(m.group(1))) if m else None


def detect_budget(ad):
    meta = ad.get("metadata") or {}
    for key in ("budget", "max_price", "budget_max", "price_ceiling", "under_price"):
        n = _money_number(ad.get(key)) or _money_number(meta.get(key))
        if n:
            return n
    title = str(meta.get("campaign_title") or ad.get("title") or "")
    m = re.search(r"under\s*(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)", title, re.I)
    if m:
        return int(float(m.group(1).replace(",", "")))
    return None


def indian_commas(n):
    n = str(int(n))
    if len(n) <= 3:
        return n
    last = n[-3:]
    rest = n[:-3]
    parts = []
    while len(rest) > 2:
        parts.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        parts.insert(0, rest)
    return ",".join(parts + [last])


def cutout_and_crop(pic):
    pic = pic.convert("RGBA")
    arr = np.array(pic)
    rgb = arr[:, :, :3].astype(np.int16)
    white = ((rgb.min(axis=2) > 238) & ((rgb.max(axis=2) - rgb.min(axis=2)) < 24)).astype(np.uint8)
    _, labels = cv2.connectedComponents(white, 8)
    edge_labels = np.unique(np.r_[labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]])
    bg = np.isin(labels, edge_labels) & (white > 0)
    arr[:, :, 3][bg] = 0
    out = Image.fromarray(arr, "RGBA")
    alpha = out.getchannel("A")
    bbox = alpha.getbbox()
    if bbox:
        out = out.crop(bbox)
    return out


def place_product(canvas, product, rect, fill=0.94):
    x1, y1, x2, y2 = rect
    # Ask helper for a generous source size, then crop/normalize visible object ourselves.
    pic = v5.load_product_image(product.get("image_url") or "", (x2-x1, y2-y1))
    if pic is None:
        print("WARNING: missing product image:", v5.display_name(product))
        return
    pic = cutout_and_crop(pic)
    if not pic.width or not pic.height:
        return
    max_w = max(1, int((x2-x1) * fill))
    max_h = max(1, int((y2-y1) * fill))
    scale = min(max_w / pic.width, max_h / pic.height)
    nw, nh = max(1, int(pic.width * scale)), max(1, int(pic.height * scale))
    pic = pic.resize((nw, nh), Image.Resampling.LANCZOS)
    x = x1 + (x2-x1-nw)//2
    y = y1 + (y2-y1-nh)//2
    canvas.alpha_composite(pic, (x, y))


def ellipsize(text, max_chars):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[:max(1, max_chars-1)].rstrip() + "…"


def wrap_text(text, max_chars=22, max_lines=2):
    words = re.sub(r"\s+", " ", str(text or "")).strip().split()
    if not words:
        return []
    lines, cur = [], ""
    i = 0
    while i < len(words):
        word = words[i]
        trial = word if not cur else cur + " " + word
        if len(trial) <= max_chars or not cur:
            cur = trial
            i += 1
        else:
            lines.append(cur)
            cur = ""
            if len(lines) >= max_lines - 1:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if i < len(words) and lines:
        lines[-1] = ellipsize(lines[-1] + " " + " ".join(words[i:]), max_chars)
    return lines[:max_lines]


def draw_centered_lines(draw, text, rect, size, min_size, color, bold=True, max_lines=2, stroke=0, stroke_fill=None):
    x1, y1, x2, y2 = rect
    max_chars = max(8, int((x2-x1) / max(7.0, size*0.55)))
    lines = wrap_text(text, max_chars=max_chars, max_lines=max_lines)
    if not lines:
        return
    # Keep a premium floor. If the line is still too wide, truncate instead of shrinking below min_size.
    fonts = []
    for line in lines:
        font = v5.fit(draw, line, max(12, x2-x1-8), size, min_size, bold)
        fonts.append(font)
    line_gap = max(2, int(size * 0.08))
    heights = []
    for font in fonts:
        box = draw.textbbox((0,0), "Ag", font=font)
        heights.append(box[3]-box[1])
    total = sum(heights) + line_gap*(len(lines)-1)
    y = (y1+y2-total)//2
    for line, font, h in zip(lines, fonts, heights):
        draw.text(((x1+x2)//2, y+h//2), line, font=font, fill=color, anchor="mm", stroke_width=stroke, stroke_fill=stroke_fill or color)
        y += h + line_gap


def draw_one_line(draw, text, rect, size, min_size, color, bold=True):
    x1, y1, x2, y2 = rect
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return
    # Hard cap preserves hierarchy; truncate before using tiny typography.
    font = v5.fit(draw, text, max(12, x2-x1-8), size, min_size, bold)
    # If the helper still cannot fit at min size, ellipsize progressively.
    probe = text
    while len(probe) > 4 and draw.textbbox((0,0), probe, font=font)[2] > (x2-x1-8):
        probe = ellipsize(probe[:-2], max(4, len(probe)-2))
    draw.text(((x1+x2)//2, (y1+y2)//2), probe, font=font, fill=color, anchor="mm")


def normalize_spec(s):
    s = re.sub(r"\s+", " ", str(s or "")).strip(" •|-_")
    replacements = [
        (r"bluetooth calling", "BT Calling"),
        (r"water resistance", "Water Resist."),
        (r"water resistant", "Water Resist."),
        (r"health features?", "Health"),
        (r"heart rate", "Heart Rate"),
        (r"battery life", "Battery"),
        (r"hours? playtime", "Hr Playtime"),
        (r"storage capacity", "Storage"),
        (r"energy rating", "Energy Rating"),
        (r"revolutions per minute", "RPM"),
    ]
    for pat, rep in replacements:
        s = re.sub(pat, rep, s, flags=re.I)
    s = re.sub(r"\b([0-9]+(?:\.[0-9]+)?)\s*(?:inch|inches)\b", r'\1"', s, flags=re.I)
    return ellipsize(s, 22)


def choose_specs(product, profile, count=4):
    raw = v5.product_specs(product, 12) or []
    vals = []
    seen = set()
    for r in raw:
        v = normalize_spec(v5.compact_spec(r))
        key = _norm(v)
        if v and key not in seen:
            seen.add(key)
            vals.append(v)
    if not vals:
        return []
    priority = profile.get("priority") or []
    scored = []
    for idx, v in enumerate(vals):
        nv = _norm(v)
        best = 999
        for pidx, kw in enumerate(priority):
            if _norm(kw) in nv:
                best = min(best, pidx)
        scored.append((best, idx, v))
    selected = []
    for best, idx, v in sorted(scored, key=lambda x: (x[0], x[1])):
        if best < 999 and v not in selected:
            selected.append(v)
            if len(selected) >= count:
                break
    for v in vals:
        if len(selected) >= count:
            break
        if v not in selected:
            selected.append(v)
    return selected[:count]


def spec_code(text):
    n = _norm(text)
    checks = [
        (["display", "inch", "screen"], "DISP"),
        (["battery", "playtime"], "BAT"),
        (["bluetooth", "calling"], "BT"),
        (["water", "ip68", "ip67"], "IP"),
        (["heart", "spo2", "health"], "HLT"),
        (["processor", "cpu", "chip"], "CPU"),
        (["ram", "memory"], "RAM"),
        (["storage", "ssd"], "SSD"),
        (["camera", "mp"], "CAM"),
        (["star", "energy"], "STAR"),
        (["watt", "power"], "W"),
        (["capacity", "litre", "liter", "kg"], "CAP"),
        (["rpm", "speed"], "RPM"),
        (["ro", "uv", "uf", "tds", "filter"], "RO"),
        (["sound", "driver", "bass"], "AUD"),
        (["resolution", "4k"], "4K"),
    ]
    for words, code in checks:
        if any(w in n for w in words):
            return code
    return "✓"


def draw_spec(draw, center, label_rect, value, top):
    if not value:
        return
    cx, cy = center
    color = WHITE if top else INK
    code = spec_code(value)
    font = v5.fit(draw, code, 34, 10 if len(code)>2 else 13, 8, True)
    draw.text((cx, cy), code, font=font, fill=color, anchor="mm")
    x1,y1,x2,y2 = label_rect
    draw_centered_lines(draw, value, label_rect, 9 if top else 8, 7, color if top else BOTTOM_SPEC, False, 2)


def draw_header(draw, category_label, budget, tagline):
    # Reference-style hierarchy: large white category line, large yellow budget line, black subtitle on yellow strip.
    draw_centered_lines(draw, f"Best {category_label}", (90, 120, 760, 216), 53, 30, WHITE, True, 1, stroke=2, stroke_fill=(18, 0, 70))
    second = f"Under ₹{indian_commas(budget)}" if budget else "Top 5 Best Picks"
    draw_centered_lines(draw, second, (90, 205, 760, 310), 61, 34, YELLOW, True, 1, stroke=2, stroke_fill=(74, 28, 0))
    draw_centered_lines(draw, tagline, (160, 313, 744, 371), 24, 15, INK, True, 1)

    benefits = [
        ("Compare Prices", "Across Top Websites"),
        ("Latest Models", "& Real Prices"),
        ("Top Rated Picks", ""),
        ("Best Deals", "in Your Budget"),
    ]
    boxes = [(830, 163, 988, 217), (830, 231, 988, 285), (830, 299, 988, 353), (830, 367, 988, 421)]
    for (line1, line2), box in zip(benefits, boxes):
        x1,y1,x2,y2 = box
        # Leave icon area on the left untouched.
        tx1 = x1 + 12
        if line2:
            draw_centered_lines(draw, line1, (tx1, y1+4, x2-5, y1+28), 15, 11, INK, True, 1)
            draw_centered_lines(draw, line2, (tx1, y1+26, x2-5, y2-2), 12, 9, INK, False, 1)
        else:
            draw_centered_lines(draw, line1, (tx1, y1+8, x2-5, y2-5), 15, 11, INK, True, 1)


def draw_product(canvas, product, slot, profile, rank):
    place_product(canvas, product, slot["image"], fill=0.96 if rank == 1 else 0.93)
    draw = ImageDraw.Draw(canvas)
    top = slot["top"]
    name_color = WHITE if top else INK
    merchant_color = WHITE if top else INK

    draw_centered_lines(
        draw, v5.display_name(product), slot["name"],
        22 if rank == 1 else (18 if top else 15),
        15 if rank == 1 else (13 if top else 11),
        name_color, True, 2 if rank == 1 else 1
    )
    draw_one_line(draw, v5.product_price(product), slot["price"], 34 if rank == 1 else (29 if top else 22), 22 if top else 16, INK, True)
    retailer = str(v5.retailer(product) or "").strip()
    draw_one_line(draw, retailer, slot["merchant"], 17 if rank == 1 else (14 if top else 12), 10, merchant_color, True)

    specs = choose_specs(product, profile, 4)
    for i in range(4):
        value = specs[i] if i < len(specs) else ""
        draw_spec(draw, slot["spec_centers"][i], slot["spec_labels"][i], value, top)


def render(ad):
    if not MASTER.is_file():
        raise FileNotFoundError(MASTER)

    category_key, profile = detect_category(ad)
    budget = detect_budget(ad)

    ranked = {}
    for i, product in enumerate(ad.get("products") or [], 1):
        rank = int(product.get("rank") or i)
        if rank in ranked:
            raise ValueError(f"Duplicate product rank: {rank}")
        ranked[rank] = product
    missing = [r for r in range(1,6) if r not in ranked]
    if missing:
        raise ValueError(f"Five ranked products required; missing ranks: {missing}")

    canvas = Image.open(MASTER).convert("RGBA")
    if canvas.size != (1024, 1536):
        raise ValueError(f"Wrong master size: {canvas.size}; expected 1024x1536")

    draw = ImageDraw.Draw(canvas)
    draw_header(draw, profile["label"], budget, profile["tagline"])

    # Preserve rank positions from the payload. Layout is frozen; data changes only.
    for rank in (2, 3, 4, 5, 1):
        draw_product(canvas, ranked[rank], SLOTS[rank], profile, rank)

    OUT.mkdir(parents=True, exist_ok=True)
    adid = ad.get("source_ad_id") or "trustfolio"
    dest = OUT / f"{adid}_final_v12_1024x1536.png"
    canvas.convert("RGB").save(dest, optimize=True)
    print("V12 UNIVERSAL QA IMAGE:", dest)
    print("CATEGORY:", category_key, "| LABEL:", profile["label"], "| BUDGET:", budget)
    print("LAYOUT: FROZEN | DATA: DYNAMIC | NOT PUBLISHED")
    return dest


if __name__ == "__main__":
    payload = Path(sys.argv[1]) if len(sys.argv) > 1 else ADS / "trustfolio_infographic_payload_v1.json"
    adid = sys.argv[2] if len(sys.argv) > 2 else "tf-aa5900f0c166"
    data = json.loads(payload.read_text(encoding="utf-8"))
    ad = next((x for x in data.get("ads", []) if x.get("source_ad_id") == adid), None)
    if ad is None:
        raise SystemExit(f"Ad not found: {adid}")
    render(ad)
