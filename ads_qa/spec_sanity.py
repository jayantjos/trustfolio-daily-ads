"""Conservative visual-only sanity checks for product specifications.

These checks never rewrite the TrustFolio website, backend or product records.
They only stop obviously implausible claims from appearing in ads. If unsure,
omit the claim rather than invent a replacement.
"""
import re


def is_sane_spec(category, key, value):
    text = str(value or "").strip()
    if not text:
        return False
    name = str(category or "").casefold().replace(" ", "").replace("-", "")
    if "smartwatch" not in name:
        return True
    context = (str(key or "") + " " + text).casefold()
    if not re.search(r"\b(display|screen|dial|inch|inches)\b|[\u2033\"]", context):
        return True
    # A smartwatch cannot have a 35/40-inch display. Accept normal watch
    # diagonals; reject out-of-scale entries in inches, cm or mm. This rule
    # checks claims, not underlying source data.
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:inches?|inch|in\b|[\u2033\"])", context):
        if float(match.group(1)) > 4.0:
            return False
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*cm\b", context):
        if float(match.group(1)) > 10.2:
            return False
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*mm\b", context):
        if float(match.group(1)) > 102:
            return False
    return True
