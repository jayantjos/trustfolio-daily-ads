"""Single-source, category-specific TrustFolio infographic subtitle resolver.

Loads literal copy from the already-approved renderer_v12_helper.py category
profiles without importing Playwright, OpenCV, or any production dependencies.
No website, scraper, product values, or fixed template geometry are changed.
"""
import ast
import re
from pathlib import Path

PROFILES_PATH = Path(__file__).resolve().parents[1] / "renderer_v12_helper.py"
GENERIC = "Top 5 Picks for Features, Quality & Value"
SAME_PRODUCT_COMPARISON = "Compare One Product Across Retailers"


def _norm(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _profile_copy():
    tree = ast.parse(PROFILES_PATH.read_text(encoding="utf-8"), filename=str(PROFILES_PATH))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "CATEGORY_PROFILES"
            for target in node.targets
        ):
            profiles = ast.literal_eval(node.value)
            if len(profiles) < 20:
                raise ValueError("Expected canonical 20-category TrustFolio copy")
            return profiles
    raise ValueError("Canonical category profiles not found")


def category_tagline(category, *, ad_type=""):
    if str(ad_type or "").strip() == "price_comparison":
        return SAME_PRODUCT_COMPARISON
    normalized = _norm(category)
    if not normalized:
        return GENERIC
    profiles = _profile_copy()
    # Rank one exact canonical slug or alias first; never use another
    # category's last-selected tagline or a global smartwatch default.
    for slug, profile in profiles.items():
        choices = (slug, profile["label"], *profile["aliases"])
        if any(_norm(choice) == normalized for choice in choices):
            return profile["tagline"]
    return GENERIC
