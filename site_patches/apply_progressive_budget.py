#!/usr/bin/env python3
"""Prepare a progressive policy on an isolated copy of the current backend."""
import argparse
from pathlib import Path


def once(source, old, new):
    if source.count(old) != 1:
        raise RuntimeError(f"Backend compatibility gate failed at {old[:90]!r}")
    return source.replace(old, new, 1)


def patch(root, assets):
    ranker_path = root / "services/ProductRecommendationService.js"
    source = ranker_path.read_text()
    addition = """
async function getBudgetNearCandidates(categorySlug, budgetCap, options = {}) {
  const min = Math.ceil(budgetCap * 0.5);
  const brand = typeof options.brand === 'string' ? options.brand.trim() : '';
  const { capped, totalMatches } = await fetchProductsInBudgetWindow(
    categorySlug, min, budgetCap, budgetCap, { brand, candidateLimit: 100 });
  const qualityRanked = orderPickedByRatingThenSpecs(categorySlug, capped.filter(hasUsableProductImage));
  // Preserve the existing quality order within each five-percent budget band.
  const band = (p) => Math.floor((budgetCap - resolveProductPrice(p)) / (budgetCap * 0.05) + 1e-9);
  qualityRanked.sort((a, b) => band(a) - band(b));
  return { products: toProductDtos(qualityRanked, { categorySlug, requestedBrand: brand }),
    truncated: totalMatches >= 100 };
}

"""
    source = once(source, "module.exports = {\n", addition + "module.exports = {\n  getBudgetNearCandidates,\n")
    source = once(source,
        "Number.isFinite(configuredDirectLimit) && configuredDirectLimit > 0 ? configuredDirectLimit : 300\n",
        "Number.isFinite(configuredDirectLimit) && configuredDirectLimit > 0 ? configuredDirectLimit : 300,\n      options.candidateLimit || Infinity\n")
    source = once(source, "const fastLimit = Math.min(scanCap, getFastBudgetCandidateLimit());",
        "const fastLimit = Math.min(scanCap, getFastBudgetCandidateLimit(), options.candidateLimit || Infinity);")
    source = once(source, "const fallbackLimit = Math.min(scanCap, getLegacyScanLimit());",
        "const fallbackLimit = Math.min(scanCap, getLegacyScanLimit(), options.candidateLimit || Infinity);")
    # This patch never edits the campaign helper or its exact-ID ranker branch.
    ranker_path.write_text(source)
    (root / "services/BudgetNearRecommendationService.js").write_text(
        (assets / "BudgetNearRecommendationService.js").read_text())
    controller_path = root / "controllers/ProductController.js"
    controller = controller_path.read_text()
    controller = once(controller,
        "const LiveBudgetRecommendationService = require('../services/LiveBudgetRecommendationService');",
        "const LiveBudgetRecommendationService = require('../services/BudgetNearRecommendationService');")
    controller = once(controller,
        "const topCacheKey = `cat-guard-live-budget-v1|${normalizedCategory}|${exactSmartphoneBudgetKey}|${limit}|${brandKey}`;",
        """const campaignRequest = normalizedCategory === 'smart-phones' && Number(budget) === 15000 && !brandKey;
  const cachePolicy = campaignRequest ? 'cat-guard-live-budget-v1' : 'progressive-budget-near-v1';
  const cacheBudget = campaignRequest ? exactSmartphoneBudgetKey : Number(budget);
  const topCacheKey = `${cachePolicy}|${normalizedCategory}|${cacheBudget}|${limit}|${brandKey}`;""")
    controller = once(controller,
        "if (topCacheHit && Date.now() - topCacheHit.at < Math.min(topProductsResponseCacheTtlMs(), 30000)) {",
        """if (topCacheHit && Date.now() - topCacheHit.at < Math.min(topProductsResponseCacheTtlMs(), 30000) &&
    (!topCacheHit.value?.data?.priceVerificationExpiresAt || Date.now() < topCacheHit.value.data.priceVerificationExpiresAt)) {""")
    controller = once(controller, "    const response = {\n      category,", """    if (recommendation.selectionPolicy === 'progressive-budget-near-v1') {
      fallbackMessage = recommendation.expansionApplied
        ? `Search expanded to ${formattedWindowMin}–${formattedWindowMax} to find verified products.` : null;
      message = `Found ${topProducts.length} verified products between ${formattedWindowMin} and ${formattedWindowMax}.`;
      selection_note = 'Search prefers products near your budget, then expands in ten-percent steps down to half your budget. Quality and retailer diversity apply within nearby price bands.';
    }

    const response = {
      ...(recommendation.selectionPolicy ? {
        selectionPolicy: recommendation.selectionPolicy,
        originalBudget: recommendation.originalBudget,
        initialPriceWindow: recommendation.initialPriceWindow,
        finalPriceWindow: recommendation.finalPriceWindow,
        selectionWaves: recommendation.livePriceWaves,
        expansionApplied: recommendation.expansionApplied,
        eligibleCandidateCount: recommendation.eligibleCandidateCount,
        initialWindowCandidateCount: recommendation.initialWindowCandidateCount,
        catalogCandidateCount: recommendation.catalogCandidateCount,
        catalogCandidateCountLimited: recommendation.catalogCandidateCountLimited,
        priceVerificationStatus: recommendation.priceVerificationStatus,
        priceVerificationExpiresAt: recommendation.priceVerificationExpiresAt,
        verificationFailures: recommendation.verificationFailures,
        stopReason: recommendation.stopReason,
        livePriceBatches: recommendation.livePriceBatches,
        selectionElapsedMs: recommendation.selectionElapsedMs,
      } : {}),
      category,""")
    controller_path.write_text(controller)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", type=Path, required=True)
    args = parser.parse_args()
    patch(args.backend, Path(__file__).parent)
