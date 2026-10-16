"""Variant-specific TrustFolio premium Instagram campaign hero copy.

The fixed premium colors/podiums/rank geometry remain frozen. Only copy
derived from the source website category, verified brand, budget and selected
advertisement type changes.
"""
import re

SHORT_CATEGORY = {
    "smart-phones":"Phones",
    "smart-tvs":"TVs",
    "laptop":"Laptops",
    "laptops":"Laptops",
    "smartwatches":"Watches",
    "washing-machines":"Washers",
    "washing-machine":"Washers",
    "headphones-earbuds":"Earbuds",
}


def campaign_hero(slug,label,ad_type,brand=""):
    label=str(label or "").strip() or "Products"
    slug=str(slug or "").strip().lower()
    brand=str(brand or "").strip()
    if ad_type=="brand_recommendation":
        if not brand:
            raise ValueError("Brand-specific creative is missing the actual verified brand")
        # Brand appears visibly on image; shorter category word avoids
        # replacing the approved premium angled title region.
        if any(ch in brand for ch in ("<",">","\n","\r")):
            raise ValueError("Unsafe brand headline")
        return f"Best {brand} {SHORT_CATEGORY.get(slug,label)}"
    if ad_type=="top5_comparison":
        return f"Compare {label}"
    return f"Best {label}"


def headline_font_size(text):
    # Conservative length-based font size keeps one line inside the angled
    # purple ribbon rather than pushing into the benefits pills.
    n=len(str(text))
    if not n or n>46:
        raise ValueError("Premium title cannot fit in one line")
    return min(72,max(35,int(1160/max(n,1))))


def campaign_subtitle(category_copy,ad_type):
    line=str(category_copy or "")
    if ad_type=="top5_comparison":
        return line.replace("Top 5 Picks for","Compare Picks for",1)
    return line
