#!/usr/bin/env python3
"""Opt-in temporary campaign pricing for exact unbranded ₹15,000 smartphones.

Apply ONLY to a staging copy of the backend already containing the exact-five override.
Does not change the database, ranking, retailer workers, or other budgets.
"""
import argparse
from pathlib import Path

IDS = (
    "69f9e9f56529299d30426ac8",
    "69f9ea1f6529299d30426ae4",
    "6a9e4a2e0933a0daedaddd80",
    "6aa56d332bb194728fab44c3",
    "6a2ed790ee20fca78fefdfde",
)
PRICES = (14489, 14703, 12799, 14999, 13999)

def patch(root):
    path = root / "services/LiveBudgetRecommendationService.js"
    src = path.read_text()
    anchor = "    let liveRows;\n    if (exactSmartphoneBudget) {"
    if src.count(anchor) != 1:
        raise RuntimeError("Exact-15000 override absent or source revision unexpected; abort")
    replacement = """    let liveRows;
    const campaignMode = exactSmartphoneBudget &&
      process.env.TF_SMARTPHONE_15000_CAMPAIGN_FIXED === 'true';
    if (campaignMode) {
      // Only the approved five, and only while the explicit campaign flag is on.
      // No retailer/Worker request. These are fixed campaign prices, NOT live prices.
      const fixed = new Map([
        ['69f9e9f56529299d30426ac8', 14489],
        ['69f9ea1f6529299d30426ae4', 14703],
        ['6a9e4a2e0933a0daedaddd80', 12799],
        ['6aa56d332bb194728fab44c3', 14999],
        ['6a2ed790ee20fca78fefdfde', 13999],
      ]);
      if (ids.some((id) => !fixed.has(String(id)))) {
        throw new Error('Unexpected product ID in campaign mode');
      }
      liveRows = ids.map((id) => ({
        id: String(id),
        deleted: false,
        live: {status: 'campaign_fixed', price_inr: fixed.get(String(id)),
          in_stock: null},
      }));
    } else if (exactSmartphoneBudget) {"""
    src = src.replace(anchor, replacement)
    old = "      if (exactSmartphoneBudget && (live?.status !== 'ok' || live.in_stock === false)) continue;"
    new = """      if (exactSmartphoneBudget && !campaignMode &&
          (live?.status !== 'ok' || live.in_stock === false)) continue;"""
    if src.count(old) != 1:
        raise RuntimeError("Expected exact-15000 live safety anchor missing; abort")
    src = src.replace(old, new)
    old2 = "      if (live?.status === 'ok') {"
    new2 = """      if (campaignMode && live?.status === 'campaign_fixed') {
        displayPrice = Number(live.price_inr);
        priceSource = 'campaign_fixed_not_live';
      } else if (live?.status === 'ok') {"""
    if src.count(old2) != 1:
        raise RuntimeError("Expected live-price mapping anchor missing; abort")
    src = src.replace(old2, new2)
    old3 = "    livePriceRefreshCompleted: true,"
    new3 = """    livePriceRefreshCompleted: !(
      category === 'smart-phones' && Number(budgetInINR) === 15000 &&
      !String(opts.brand || '').trim() &&
      process.env.TF_SMARTPHONE_15000_CAMPAIGN_FIXED === 'true'
    ),
    campaignPriceDisclosure: category === 'smart-phones' &&
      Number(budgetInINR) === 15000 && !String(opts.brand || '').trim() &&
      process.env.TF_SMARTPHONE_15000_CAMPAIGN_FIXED === 'true'
      ? 'Campaign reference price; not live verified. Check retailer before purchase.'
      : null,"""
    if src.count(old3) != 1:
        raise RuntimeError("Expected metadata anchor missing; abort")
    src = src.replace(old3, new3)
    path.write_text(src)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--staging-backend', type=Path, required=True)
    args = ap.parse_args()
    patch(args.staging_backend)
