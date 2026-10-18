'use strict';

/**
 * Reuse the existing MongoDB ranker; refresh live prices BEFORE choosing final five.
 * Never insert an unranked/random product. Additional waves ask the same ranker
 * for the next best products, excluding IDs already examined.
 */
const OriginalRanker = require('./ProductRecommendationService');
const LivePriceService = require('./LivePriceService');
const MAX_WAVES = 4; // at most 20 candidate IDs / request

function goodPrice(value, budgetCap) {
  const p = Number(value);
  return Number.isFinite(p) && p > 0 && p <= budgetCap;
}

async function getTopProductsForCategoryAndBudget(category, budgetInINR, opts = {}, dependencies = {}) {
  const ranker = dependencies.ranker || OriginalRanker;
  const priceService = dependencies.prices || LivePriceService;
  const budgetCap = Math.floor(Number(budgetInINR));
  const limit = Math.min(5, Math.max(1, Number(opts.limit) || 5));
  if (!Number.isFinite(budgetCap) || budgetCap <= 0) {
    throw new Error('Invalid budget for live price ranking');
  }

  const inspected = new Set();
  const qualified = [];
  let initial = null;
  let latest = null;
  let refreshedCount = 0;
  let waveCount = 0;

  for (let wave = 0; wave < MAX_WAVES && qualified.length < limit; wave++) {
    waveCount++;
    const rec = await ranker.getTopProductsForCategoryAndBudget(category, budgetCap, {
      ...opts,
      limit,
      excludeProductIds: [...inspected],
    });
    if (!initial) initial = rec;
    latest = rec;
    const batch = (rec.products || []).filter((p) => {
      const id = String(p.id || '');
      if (!id || inspected.has(id)) return false;
      inspected.add(id);
      return true;
    });
    if (!batch.length) break;

    const ids = batch.map((p) => String(p.id));
    const liveRows = await priceService.getLivePrices(ids);
    // Cannot confirm product identity if refresh fails. Return no stale candidates.
    if (!Array.isArray(liveRows)) throw new Error('Live price API response invalid');
    const byId = new Map();
    for (const row of liveRows) {
      const id = String(row && row.id || '');
      if (!id || byId.has(id) || !ids.includes(id)) throw new Error('Live price API returned mismatched IDs');
      byId.set(id, row);
    }
    if (byId.size !== ids.length) throw new Error('Live price API returned incomplete IDs');
    refreshedCount += ids.length;

    for (const candidate of batch) {
      const row = byId.get(String(candidate.id));
      const live = row.live || null;
      if (row.deleted || live?.status === 'out_of_stock') continue;

      let displayPrice = candidate.price_inr;
      let priceSource = 'website_catalog';
      if (live?.status === 'ok') {
        displayPrice = Number(live.price_inr);
        priceSource = 'website_live_price_api';
      }
      if (!goodPrice(displayPrice, budgetCap)) continue;
      qualified.push({
        ...candidate,
        price_inr: Number(displayPrice),
        price_source: priceSource,
        live_price_status: live?.status || null,
      });
      if (qualified.length >= limit) break;
    }
  }

  const original = initial || latest || {
    products: [],
    totalMatches: 0,
    priceWindow: { min: 0, max: budgetCap },
    matchType: 'none',
  };
  const products = qualified.slice(0, limit).map((p, i) => ({ ...p, rank: i + 1 }));
  const requestedBrand = original.requestedBrand || null;
  const brandMatchCount = requestedBrand
    ? products.filter((p) => p.isRequestedBrandMatch === true).length : 0;
  const similarFillCount = requestedBrand ? products.length - brandMatchCount : 0;
  const fallbackApplied = requestedBrand
    ? similarFillCount > 0 : Boolean(original.fallbackApplied);
  let matchType = original.matchType || 'none';
  if (!products.length) matchType = 'none';
  else if (requestedBrand) {
    if (!brandMatchCount) matchType = 'within_budget_brand_fallback';
    else if (similarFillCount) matchType = 'within_budget_and_brand_partial';
    else matchType = 'within_budget_and_brand';
  }

  return {
    ...original,
    products,
    matchType,
    fallbackApplied,
    partialBrandFill: Boolean(requestedBrand && brandMatchCount && similarFillCount),
    brandMatchCount,
    similarFillCount,
    livePriceRefreshCompleted: true,
    livePriceCandidatesChecked: refreshedCount,
    livePriceWaves: waveCount,
  };
}

module.exports = { getTopProductsForCategoryAndBudget };
