#!/usr/bin/env python3
"""Patch an isolated COPY of the TrustFolio site, never the original automatically."""
import argparse
from pathlib import Path

def once(content, before, after, name):
    count = content.count(before)
    if count != 1:
        raise RuntimeError(f"Unsafe source drift in {name}: expected 1 match, got {count}")
    return content.replace(before, after, 1)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',required=True,help='isolated copy of website source, NOT the production tree')
    args=parser.parse_args()
    root=Path(args.root).resolve()
    if str(root).startswith(str(Path.home()/'apps/trustfolio')) or root == Path.home():
        raise RuntimeError('Refusing to patch live website directory')
    scripts={}

    service='node-backend/services/ProductRecommendationService.js'
    text=(root/service).read_text()
    text=once(text,
      'const cap = Math.min(Math.max(Number(resultLimit) || 5, 1), 5);',
      'const cap = Math.min(Math.max(Number(resultLimit) || 5, 1), 15);',service)
    text=once(text,
      '? Math.min(options.limit, 5)',
      '? Math.min(options.limit, 15)',service)
    scripts[service]=text

    controller='node-backend/controllers/ProductController.js'
    text=(root/controller).read_text()
    text=once(text,
      "const ProductRecommendationService = require('../services/ProductRecommendationService');",
      "const ProductRecommendationService = require('../services/ProductRecommendationService');\n"
      "const LivePriceService = require('../services/LivePriceService');\n"
      "const { selectLiveBudgetTop } = require('../services/LiveBudgetSelection');",controller)
    text=once(text,
      "const limit = Math.min(parseInt(req.query.limit, 10) || 5, 5);",
      "const limit = Math.min(parseInt(req.query.limit, 10) || 5, 5);\n"
      "    const liveBudgetMode = req.query.live_budget === '1';",controller)
    text=once(text,
      "const topCacheKey = `cat-guard-v4|${normalizedCategory}|${Math.floor(Number(budget))}|${limit}|${brandKey}`;",
      "const topCacheKey = `cat-guard-live-v1|${normalizedCategory}|${Math.floor(Number(budget))}|${limit}|${brandKey}|${liveBudgetMode}`;",controller)
    text=once(text,
      "Date.now() - topCacheHit.at < topProductsResponseCacheTtlMs()",
      "Date.now() - topCacheHit.at < (liveBudgetMode ? 30000 : topProductsResponseCacheTtlMs())",controller)
    text=once(text,
      "    { limit, ...(brand ? { brand } : {}) }",
      "    { limit: liveBudgetMode ? Math.min(limit * 3, 15) : limit, ...(brand ? { brand } : {}) }",controller)
    old='''const budgetCap = Math.floor(Number(budget));
let topProducts = recommendation.products || [];
topProducts = topProducts
  .filter((p) => {
    const pr = Number(p.price_inr);
    return Number.isFinite(pr) && pr <= budgetCap;
  })
  .map((p, idx) => ({ ...p, rank: idx + 1 }));

let matchType = recommendation.matchType || 'none';
if (topProducts.length === 0) matchType = 'none';

const fallbackApplied = Boolean(recommendation.fallbackApplied);
    const partialBrandFill = Boolean(recommendation.partialBrandFill);
    const brandMatchCount = recommendation.brandMatchCount ?? 0;
    const similarFillCount = recommendation.similarFillCount ?? 0;'''
    new='''const budgetCap = Math.floor(Number(budget));
let topProducts = recommendation.products || [];
if (liveBudgetMode && topProducts.length) {
  // Batch refreshes up to 15 shortlisted products in parallel before final Top-5 selection.
  // Replaces candidates that became expensive/out-of-stock with next ranked eligible rows.
  // Errors fail closed instead of showing unchecked prices above a user budget.
  const liveRows = await LivePriceService.getLivePrices(topProducts.map((p) => p.id));
  topProducts = selectLiveBudgetTop(topProducts, liveRows, budgetCap, limit);
} else {
  topProducts = topProducts
    .filter((p) => {
      const pr = Number(p.price_inr);
      return Number.isFinite(pr) && pr > 0 && pr <= budgetCap;
    })
    .map((p, idx) => ({ ...p, rank: idx + 1 }));
}

let matchType = recommendation.matchType || 'none';
if (topProducts.length === 0) matchType = 'none';
if (liveBudgetMode && brand && topProducts.length) {
  const matching = topProducts.filter((p) => p.isRequestedBrandMatch === true).length;
  matchType = matching === topProducts.length ? 'within_budget_and_brand'
    : matching === 0 ? 'within_budget_brand_fallback' : 'within_budget_and_brand_partial';
}

const fallbackApplied = liveBudgetMode && brand
  ? matchType === 'within_budget_brand_fallback' || matchType === 'within_budget_and_brand_partial'
  : Boolean(recommendation.fallbackApplied);
    const partialBrandFill = liveBudgetMode && brand
      ? matchType === 'within_budget_and_brand_partial'
      : Boolean(recommendation.partialBrandFill);
    const brandMatchCount = liveBudgetMode && brand
      ? topProducts.filter((p) => p.isRequestedBrandMatch === true).length
      : (recommendation.brandMatchCount ?? 0);
    const similarFillCount = liveBudgetMode && brand
      ? topProducts.filter((p) => p.isRequestedBrandMatch === false).length
      : (recommendation.similarFillCount ?? 0);'''
    text=once(text,old,new,controller)
    scripts[controller]=text

    api='trustfolio-main/src/services/api.service.ts'
    text=(root/api).read_text()
    text=once(text,
      "      budget: String(budget),",
      "      budget: String(budget),\n      live_budget: '1',",api)
    scripts[api]=text

    table='trustfolio-main/src/components/ProductsTable.tsx'
    text=(root/table).read_text()
    text=once(text,
      "interface ProductsTableProps {\n    products: Product[];\n}",
      "interface ProductsTableProps {\n    products: Product[];\n    budgetCap?: number;\n}",table)
    text=once(text,
      "export default function ProductsTable({ products }: ProductsTableProps)",
      "export default function ProductsTable({ products, budgetCap }: ProductsTableProps)",table)
    text=once(text,
      "const visibleProducts = sortedProducts.filter((p) => !livePrices[p.id]?.deleted);",
      """const visibleProducts = sortedProducts.filter((p) => {
        const row = livePrices[p.id];
        if (row?.deleted || row?.live?.status === 'out_of_stock') return false;
        const price = row?.live?.status === 'ok'
          ? Number(row.live.price_inr) : Number(p.price_inr);
        return Number.isFinite(price) && price > 0 &&
          (!budgetCap || price <= budgetCap);
    }).slice(0, 5);""",table)
    scripts[table]=text

    page='trustfolio-main/src/app/category/[slug]/products/page.tsx'
    text=(root/page).read_text()
    text=once(text,
      "<ProductsTable products={filteredProducts} />",
      "<ProductsTable products={filteredProducts} budgetCap={budgetCapFloored} />",page)
    scripts[page]=text

    helper=Path(__file__).resolve().with_name('live_budget_select.js')
    scripts['node-backend/services/LiveBudgetSelection.js']=helper.read_text()
    for rel,body in scripts.items():
      dest=root/rel
      dest.parent.mkdir(parents=True,exist_ok=True)
      dest.write_text(body)
      print('STAGED_WEBSITE_FILE='+rel)
    print('STAGING_PATCH_APPLIED_NO_PRODUCTION_WRITES=true')

if __name__=='__main__':main()
