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
  const categoryFilter = buildExactCategoryFilter(categorySlug);
  if (!categoryFilter) return { products: [], truncated: false };
  const min = Math.ceil(budgetCap * 0.5);
  const filters = [categoryFilter, buildBudgetPriceFilter(min, budgetCap),
    { $or: [{ isActive: true }, { isActive: null }] }];
  const brand = typeof options.brand === 'string' ? options.brand.trim() : '';
  const query = { $and: appendBrandToFilterParts(filters, brand, categorySlug) };
  const docs = await MyProduct.find(query).select(RANKING_FIELDS)
    .sort({ price_inr: -1, _id: 1 }).limit(500).maxTimeMS(getBudgetQueryMaxTimeMS()).lean();
  const { capped } = filterBudgetCandidates(docs, categorySlug, min, budgetCap, 500, { brand });
  const qualityRanked = orderPickedByRatingThenSpecs(categorySlug, capped.filter(hasUsableProductImage));
  // Preserve the existing quality order within each five-percent budget band.
  const band = (p) => Math.floor((budgetCap - resolveProductPrice(p)) / (budgetCap * 0.05) + 1e-9);
  qualityRanked.sort((a, b) => band(a) - band(b));
  return { products: toProductDtos(qualityRanked, { categorySlug, requestedBrand: brand }),
    truncated: docs.length === 500 };
}

"""
    source = once(source, "module.exports = {\n", addition + "module.exports = {\n  getBudgetNearCandidates,\n")
    # This patch never edits the campaign helper or its exact-ID ranker branch.
    ranker_path.write_text(source)
    (root / "services/BudgetNearRecommendationService.js").write_text(
        (assets / "BudgetNearRecommendationService.js").read_text())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", type=Path, required=True)
    args = parser.parse_args()
    patch(args.backend, Path(__file__).parent)
