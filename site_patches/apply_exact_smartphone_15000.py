#!/usr/bin/env python3
"""Prepare the exact smartphone budget override in a staging backend copy."""
import argparse
from pathlib import Path


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"Unexpected backend revision at anchor: {old}")
    return source.replace(old, new, 1)


def patch(root):
    helper = root / "services/LiveBudgetRecommendationService.js"
    ranker = root / "services/ProductRecommendationService.js"
    controller = root / "controllers/ProductController.js"

    live = replace_once(
        helper.read_text(),
        "  const inspected = new Set();",
        """  const exactSmartphoneBudget = category === 'smart-phones' &&
    Number(budgetInINR) === 15000 && !String(opts.brand || '').trim();
  const inspected = new Set();""",
    )
    live = replace_once(
        live,
        "      excludeProductIds: [...inspected],",
        "      excludeProductIds: [...inspected],\n      exactSmartphoneBudget,",
    )
    live = replace_once(
        live,
        "      if (row.deleted || live?.status === 'out_of_stock') continue;",
        """      if (row.deleted || live?.status === 'out_of_stock') continue;
      if (exactSmartphoneBudget && live?.status !== 'ok') continue;""",
    )

    ranking = replace_once(
        ranker.read_text(),
        "  if (requestedBrand) {\n    const withBrand = await loadBudgetCandidates(",
        """  if (options.exactSmartphoneBudget === true &&
      categorySlug === 'smart-phones' && budgetInINR === 15000 && !requestedBrand) {
    const ids = [
      '69f9e9f56529299d30426ac8',
      '69f9ea1f6529299d30426ae4',
      '6a9e4a2e0933a0daedaddd80',
      '6aa56d332bb194728fab44c3',
      '6a2ed790ee20fca78fefdfde',
    ].filter((id) => !excludedIds.has(id));
    const candidates = ids.length ? await fetchCandidateBatch({
      $and: [
        buildExactCategoryFilter(categorySlug),
        { _id: { $in: ids } },
        { $or: [{ isActive: true }, { isActive: null }] },
      ],
    }, ids.length) : [];
    const { capped } = filterBudgetCandidates(candidates, categorySlug, 1, budgetCap, ids.length);
    const byId = new Map(capped.map((product) => [productStableId(product), product]));
    const ordered = ids.map((id) => byId.get(id)).filter(Boolean);
    return {
      ...emptyResult,
      products: toProductDtos(ordered),
      totalMatches: ordered.length,
      priceWindow: { min: 0, max: budgetCap },
      matchType: ordered.length ? 'within_budget' : 'none',
    };
  }

  if (requestedBrand) {
    const withBrand = await loadBudgetCandidates(""",
    )

    # Separate the override cache key from non-exact budgets that floor to 15000.
    # Abort staging if the deployed controller uses a different cache contract.
    top = replace_once(
        controller.read_text(),
        'const topCacheKey = `cat-guard-live-budget-v1|${normalizedCategory}|${Math.floor(Number(budget))}|${limit}|${brandKey}`;',
        """const exactSmartphoneBudgetKey = normalizedCategory === 'smart-phones' &&
    Number(budget) === 15000 ? 'exact-15000-v1' : Math.floor(Number(budget));
  const topCacheKey = `cat-guard-live-budget-v1|${normalizedCategory}|${exactSmartphoneBudgetKey}|${limit}|${brandKey}`;""",
    )

    for path, source in ((helper, live), (ranker, ranking), (controller, top)):
        path.write_text(source)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-backend", required=True, type=Path)
    patch(parser.parse_args().staging_backend)
