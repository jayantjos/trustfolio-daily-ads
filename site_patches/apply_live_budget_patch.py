#!/usr/bin/env python3
"""Patch only the known website source revision, preserving the legacy MongoDB ranker.

Run against a *staging copy* of node-backend first. No writes to MongoDB.
A dedicated backed-up deployment process must explicitly promote these files.
"""
import argparse
from pathlib import Path

def replace_once(source, old, new, name):
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{name}: expected exactly one anchor, got {count}")
    return source.replace(old, new, 1)

def patch(root):
    root = Path(root)
    ranker_path = root / "services/ProductRecommendationService.js"
    controller_path = root / "controllers/ProductController.js"
    ranker = ranker_path.read_text(encoding="utf8")
    controller = controller_path.read_text(encoding="utf8")

    # Only exclude previously inspected MongoDB IDs. Existing category, OEM
    # brand, rating/spec scoring and 2/2/1 platform quotas remain untouched.
    ranker = replace_once(ranker,
        "  const budgetCap = Math.floor(Number(budgetInINR));\n  const { min: minBudget, max: maxFromRule } = getBudgetPriceWindow(budgetInINR);",
        "  const budgetCap = Math.floor(Number(budgetInINR));\n  const excludedIds = new Set((options.excludeProductIds || []).map(String));\n  const notInspected = (p) => !excludedIds.has(productStableId(p));\n  const { min: minBudget, max: maxFromRule } = getBudgetPriceWindow(budgetInINR);",
        "ranker exclusion support")

    ranker = replace_once(ranker,
        "const brandFiltered = withBrand.capped.filter((p) =>\n      productMatchesOemBrand(categorySlug, p.brand, requestedBrand)\n    );",
        "const brandFiltered = withBrand.capped.filter((p) =>\n      notInspected(p) && productMatchesOemBrand(categorySlug, p.brand, requestedBrand)\n    );",
        "brand exclusion")
    ranker = replace_once(ranker,
        "!pickedIds.has(productStableId(p)) &&\n            !productMatchesOemBrand(categorySlug, p.brand, requestedBrand)",
        "!pickedIds.has(productStableId(p)) &&\n            notInspected(p) &&\n            !productMatchesOemBrand(categorySlug, p.brand, requestedBrand)",
        "similar pool exclusion")
    ranker = replace_once(ranker,
        "categorySlug, withoutBrand.capped, withoutBrand.totalMatches,",
        "categorySlug, withoutBrand.capped.filter(notInspected), withoutBrand.totalMatches,",
        "all-brand fallback exclusion")
    ranker = replace_once(ranker,
        "categorySlug, loaded.capped, loaded.totalMatches,",
        "categorySlug, loaded.capped.filter(notInspected), loaded.totalMatches,",
        "budget exclusion")
    # When the near-budget candidates have all been inspected, apply the
    # original wider 0..budget fallback (not a new ranking formula).
    ranker = replace_once(ranker,
        "  if (primary.capped.length > 0 || minBudget <= 0) {\n    return {",
        "  const excluded = new Set((options.excludeProductIds || []).map(String));\n  const hasUninspected = primary.capped.some((p) => !excluded.has(productStableId(p)));\n  if (hasUninspected || minBudget <= 0) {\n    return {",
        "near-budget exhaustion fallback")
    ranker = replace_once(ranker,
        "categorySlug, minBudget, maxBudget, budgetCap, { brand: requestedBrand }",
        "categorySlug, minBudget, maxBudget, budgetCap, { brand: requestedBrand, excludeProductIds: [...excludedIds] }",
        "brand candidate query exclusion")
    ranker = replace_once(ranker,
        "categorySlug, withBrand.windowMin, withBrand.windowMax, budgetCap\n        );",
        "categorySlug, withBrand.windowMin, withBrand.windowMax, budgetCap, { excludeProductIds: [...excludedIds] }\n        );",
        "similar candidate query exclusion")
    ranker = replace_once(ranker,
        "categorySlug, minBudget, maxBudget, budgetCap\n    );",
        "categorySlug, minBudget, maxBudget, budgetCap, { excludeProductIds: [...excludedIds] }\n    );",
        "budget candidate query exclusion")
    # Brand-fallback call can be identical to the unbranded call at another
    # source location, so apply remaining exact occurrence only if present.
    brand_fallback_anchor = "    const withoutBrand = await loadBudgetCandidates(\n      categorySlug, minBudget, maxBudget, budgetCap\n    );"
    if brand_fallback_anchor in ranker:
        ranker = replace_once(ranker, brand_fallback_anchor,
            "    const withoutBrand = await loadBudgetCandidates(\n      categorySlug, minBudget, maxBudget, budgetCap, { excludeProductIds: [...excludedIds] }\n    );",
            "brand fallback query exclusion")
    # The ordinary path must pass exclusions too; unlike the previous
    # blanket pattern this exactly matches the final non-brand call.
    regular_anchor = "  const loaded = await loadBudgetCandidates(\n    categorySlug, minBudget, maxBudget, budgetCap\n  );"
    ranker = replace_once(ranker, regular_anchor,
        "  const loaded = await loadBudgetCandidates(\n    categorySlug, minBudget, maxBudget, budgetCap, { excludeProductIds: [...excludedIds] }\n  );",
        "regular query exclusion")

    controller = replace_once(controller,
        "const ProductRecommendationService = require('../services/ProductRecommendationService');",
        "const ProductRecommendationService = require('../services/ProductRecommendationService');\nconst LiveBudgetRecommendationService = require('../services/LiveBudgetRecommendationService');",
        "controller import")
    controller = replace_once(controller,
        "const topCacheKey = `cat-guard-v4|${normalizedCategory}|${Math.floor(Number(budget))}|${limit}|${brandKey}`;",
        "const topCacheKey = `cat-guard-live-budget-v1|${normalizedCategory}|${Math.floor(Number(budget))}|${limit}|${brandKey}`;",
        "cache key v5")
    controller = replace_once(controller,
        "Date.now() - topCacheHit.at < topProductsResponseCacheTtlMs()",
        "Date.now() - topCacheHit.at < Math.min(topProductsResponseCacheTtlMs(), 30000)",
        "live refresh response cache TTL")
    controller = replace_once(controller,
        "ProductRecommendationService.getTopProductsForCategoryAndBudget(\n    normalizedCategory,",
        "LiveBudgetRecommendationService.getTopProductsForCategoryAndBudget(\n    normalizedCategory,",
        "GET top five route")
    # Persist no response metadata unless the live-price overlay was successful.
    controller = replace_once(controller,
        "      catalogPriceRange,\n      message,",
        "      catalogPriceRange,\n      livePriceRefreshCompleted: recommendation.livePriceRefreshCompleted === true,\n      livePriceCandidatesChecked: recommendation.livePriceCandidatesChecked || 0,\n      message,",
        "API price-refresh audit")
    ranker_path.write_text(ranker, encoding="utf8")
    controller_path.write_text(controller, encoding="utf8")
    print("STAGING_PATCH_APPLIED_TO:", str(root))

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--backend-dir", required=True)
    args=parser.parse_args()
    patch(args.backend_dir)
