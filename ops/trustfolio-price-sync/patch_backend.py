#!/usr/bin/env python3
"""Apply minimal TrustFolio backend patches with exact-match guards and backups."""
from pathlib import Path
from datetime import datetime, timezone
import json, shutil, subprocess, sys

root = Path.home() / "apps/trustfolio/node-backend"
backup = Path.home() / "backups/trustfolio-price-sync" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
backup.mkdir(parents=True, exist_ok=True)
paths = [
    root / "services/LivePriceService.js",
    root / "services/CategoryService.js",
]
originals = {}
modified = {}

def replace_one(text, before, after, label):
    if after in text:
        return text
    if text.count(before) != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {text.count(before)}")
    return text.replace(before, after, 1)

try:
    for path in paths:
        originals[path] = path.read_text(encoding="utf8")

    live = originals[paths[0]]
    if "function isConfirmedUnavailable(live)" not in live:
        needle = "function toLive(result, prev = {}) {"
        helper = """function isConfirmedUnavailable(live) {
  if (!live || !live.status) return false;
  const status = String(live.status).toLowerCase().trim().replace(/[\\s-]+/g, '_');
  // Network/HTTP failures are not proof of a permanently unavailable product.
  if (status === 'error' || status === 'timeout' || status === 'blocked') return false;
  if (['out_of_stock', 'sold_out', 'discontinued', 'permanently_unavailable'].includes(status)) return true;
  const availability = String(live.availability || '').toLowerCase();
  if (/discontinued|sold\\s*out|out\\s*of\\s*stock|no\\s*longer\\s*available/.test(availability)) return true;
  // An ambiguous N/A, unavailable or missing listing must persist across TWO fresh checks.
  return ['not_available', 'unavailable', 'n/a', 'na', 'not_found'].includes(status)
    && (Number(live.unavailable_checks) || 0) >= 2;
}

"""
        live = replace_one(live, needle, helper + needle, "availability_classifier")
    live = replace_one(
        live,
        "  const priced = (result.status === 'ok' || result.status === 'out_of_stock') && result.priceNum > 0;",
        """  const priced = (result.status === 'ok' || result.status === 'out_of_stock') && result.priceNum > 0;
  const s = String(result.status || '').toLowerCase().trim().replace(/[\\s-]+/g, '_');
  const unavailable = ['out_of_stock', 'sold_out', 'discontinued', 'permanently_unavailable',
    'not_available', 'unavailable', 'n/a', 'na', 'not_found'].includes(s);""",
        "toLive_pricing",
    )
    live = replace_one(
        live,
        "    availability: result.availability ?? null,",
        """    availability: result.availability ?? null,
    unavailable_checks: unavailable ? (Number(prev.unavailable_checks) || 0) + 1 : 0,""",
        "unavailable_count",
    )
    live = replace_one(live, "const outOfStock = fetched.filter((d) => d.live.status === 'out_of_stock');",
        "const outOfStock = fetched.filter((d) => isConfirmedUnavailable(d.live));",
        "confirm_unavailability")
    live = replace_one(live, "deleted_reason: 'out_of_stock',",
        "deleted_reason: String(outOfStock.find((d) => d._id.equals(doc._id)).live.status || 'unavailable'),",
        "deletion_reason")
    live = replace_one(live,
        "kept.map((d) => ({ updateOne: { filter: { _id: d._id }, update: { $set: { live: d.live } } } })),",
        """kept.map((d) => {
        const fields = { live: d.live };
        // Persist actual successful live prices to MongoDB canonical catalog price.
        if (d.live.status === 'ok' && Number.isFinite(Number(d.live.price_inr))
            && Number(d.live.price_inr) > 0) {
          const price = Number(d.live.price_inr);
          fields.price = String(price);
          fields.price_inr = price;
          fields.currentPriceValue = price;
        }
        return { updateOne: { filter: { _id: d._id }, update: { $set: fields } } };
      }),""",
        "canonical_live_price_persistence")
    modified[paths[0]] = live

    cat = originals[paths[1]]
    before = """    let price = null;

    if (Number.isFinite(p.currentPriceValue) && p.currentPriceValue > 0) {
      price = p.currentPriceValue;
    } else if (Number.isFinite(p.current_price_value) && p.current_price_value > 0) {
      price = p.current_price_value;
    } else if (Number.isFinite(p.price_inr) && p.price_inr > 0) {
      price = p.price_inr;
    } else {
      price =
        extractPriceFromString(p.currentPrice)
        || extractPriceFromString(p.current_price)
        || extractPriceFromString(p.price)
        || extractPriceFromString(String(p.price_inr || ''));
    }"""
    after = """    // Canonical my_products.price must win over legacy mirrored values.
    // LivePriceService and the change-stream watcher update that field.
    let price = extractPriceFromString(p.price);

    if (!(price > 0)) {
      if (Number.isFinite(p.currentPriceValue) && p.currentPriceValue > 0) {
        price = p.currentPriceValue;
      } else if (Number.isFinite(p.current_price_value) && p.current_price_value > 0) {
        price = p.current_price_value;
      } else if (Number.isFinite(p.price_inr) && p.price_inr > 0) {
        price = p.price_inr;
      } else {
        price = extractPriceFromString(p.currentPrice)
          || extractPriceFromString(p.current_price)
          || extractPriceFromString(String(p.price_inr || ''));
      }
    }"""
    cat = replace_one(cat,before,after,"canonical_category_price")
    cat = replace_one(cat, "  if (prices.length === 0) return category;",
        """  if (prices.length === 0) {
    category.min_price = null;
    category.max_price = null;
    category.price_ranges = [];
    category.updated_at = formatDate();
    return category.save();
  }""","empty_category_bound_clear")
    modified[paths[1]] = cat

    for path in paths:
        bak = backup / path.relative_to(root)
        bak.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path,bak)
        if originals[path] != modified[path]:
            path.write_text(modified[path], encoding="utf8")
    for path in paths:
        subprocess.run(["node","--check",str(path)],check=True,stdout=subprocess.DEVNULL)
    (backup/"manifest.json").write_text(json.dumps({"modified":[str(p.relative_to(root)) for p in paths],
        "backup":str(backup)},indent=2))
    print("BACKUP_PATH",backup)
    print("BACKEND_PATCH_SYNTAX=PASS")
    print("CANONICAL_PRICE_PERSISTENCE=INSTALLED")
    print("CATEGORY_CANONICAL_SOURCE=INSTALLED")
    print("EMPTY_CATEGORY_RANGE_CLEAR=INSTALLED")
    print("CONFIRMED_UNAVAILABLE_ARCHIVE=INSTALLED")
except Exception as exc:
    for path,original in originals.items():
        if path.exists() and path.read_text(encoding="utf8") != original:
            path.write_text(original,encoding="utf8")
    print("PATCH_ROLLED_BACK",type(exc).__name__,str(exc)[:250])
    sys.exit(1)
