'use strict';

const PERCENTAGES = [90, 80, 70, 60, 50];
const MAX_CHECKS = 15;
const REQUEST_MS = 7500;
const FETCH_TIMEOUT_MS = 6000;
const inFlight = new Map();

function priceTier(price, budget) {
  return Math.floor((budget - price) / (budget * 0.05) + 1e-9);
}

function verified(row, now, freshness) {
  const live = row && row.live;
  const checked = new Date(live?.checked_at || 0).getTime();
  const priced = new Date(live?.priced_at || 0).getTime();
  return !row?.deleted && live?.status === 'ok' && live.in_stock === true &&
    Number.isFinite(checked) && Number.isFinite(priced) &&
    checked > 0 && priced > 0 && checked <= now && priced <= now &&
    now - checked <= freshness && now - priced <= freshness;
}

async function select(category, originalBudget, opts, dependencies) {
  const ranker = dependencies.ranker || require('./ProductRecommendationService');
  const prices = dependencies.prices || require('./LivePriceService');
  const clock = dependencies.now || Date.now;
  const started = clock();
  const budget = Math.floor(Number(originalBudget));
  if (!Number.isFinite(budget) || budget <= 0) throw new Error('Invalid budget');
  const limit = Math.min(5, Math.max(1, Math.floor(Number(opts.limit) || 5)));
  const configuredFreshness = Number(process.env.LIVE_PRICE_FRESH_MS || 60000);
  if (!Number.isFinite(configuredFreshness) || configuredFreshness <= 0) {
    throw new Error('Invalid live price freshness policy');
  }
  const pool = await ranker.getBudgetNearCandidates(category, budget, opts);
  const candidates = [...new Map(pool.products.map(p => [String(p.id), p])).values()];
  const checked = new Set();
  const rowsById = new Map();
  const selected = [];
  const counts = new Map();
  const rejected = {};
  let waves = 0;
  let finalMin = Math.ceil(budget * 0.9);
  let stopReason = 'minimum_window_reached';
  let liveBatches = 0;

  for (const percent of PERCENTAGES) {
    waves++;
    finalMin = Math.ceil(budget * percent / 100);
    const eligible = () => candidates.filter(p => {
      const row = rowsById.get(String(p.id));
      const price = Number(row?.live?.price_inr);
      return !selected.some(s => s.id === p.id) &&
        verified(row, clock(), configuredFreshness) && price >= finalMin && price <= budget;
    });
    let pending = candidates.filter(p => !checked.has(String(p.id)) && p.price_inr >= finalMin);
    while (selected.length + eligible().length < limit && pending.length) {
      if (checked.size >= MAX_CHECKS) { stopReason = 'candidate_limit'; break; }
      if (clock() - started > REQUEST_MS - FETCH_TIMEOUT_MS) {
        stopReason = 'time_budget'; break;
      }
      const ids = pending.slice(0, Math.min(5, MAX_CHECKS - checked.size)).map(p => String(p.id));
      ids.forEach(id => checked.add(id));
      const fetched = await prices.getLivePrices(ids);
      liveBatches++;
      if (!Array.isArray(fetched)) throw new Error('Invalid live price response');
      const returned = new Set();
      for (const row of fetched) {
        const id = String(row?.id || '');
        if (!ids.includes(id) || returned.has(id)) throw new Error('Mismatched live price IDs');
        returned.add(id);
        rowsById.set(id, row);
        if (!verified(row, clock(), configuredFreshness)) {
          const reason = row.deleted ? 'unavailable' : row.live?.status || 'verification_failed';
          rejected[reason] = (rejected[reason] || 0) + 1;
        }
      }
      if (returned.size !== ids.length) throw new Error('Incomplete live price IDs');
      pending = pending.filter(p => !checked.has(String(p.id)));
    }

    const qualityOrder = new Map(candidates.map((p, i) => [p.id, i]));
    const remaining = eligible().sort((a, b) => {
      const tierA = priceTier(Number(rowsById.get(String(a.id)).live.price_inr), budget);
      const tierB = priceTier(Number(rowsById.get(String(b.id)).live.price_inr), budget);
      return tierA - tierB || qualityOrder.get(a.id) - qualityOrder.get(b.id);
    });
    // Prefer another retailer only within the same 5% price band. Quality order
    // within each retailer remains the existing category comparator's order.
    while (remaining.length && selected.length < limit) {
      const firstTier = priceTier(Number(rowsById.get(String(remaining[0].id)).live.price_inr), budget);
      const diverse = remaining.findIndex(p =>
        priceTier(Number(rowsById.get(String(p.id)).live.price_inr), budget) === firstTier &&
        (counts.get(p.platform) || 0) < 2);
      const candidate = remaining.splice(diverse < 0 ? 0 : diverse, 1)[0];
      const live = rowsById.get(String(candidate.id)).live;
      selected.push({ ...candidate, price_inr: Number(live.price_inr),
        price_source: 'website_live_price_api', live_price_status: 'ok',
        price_verification_status: new Date(live.priced_at).getTime() < started
          ? 'fresh_cached_verified' : 'verified_live',
        availability_status: 'In Stock', in_stock: true, rank: selected.length + 1 });
      counts.set(candidate.platform, (counts.get(candidate.platform) || 0) + 1);
    }
    if (selected.length >= limit) { stopReason = 'filled'; break; }
    if (stopReason === 'candidate_limit' || stopReason === 'time_budget') break;
  }
  return {
    products: selected, totalMatches: selected.length, eligibleCandidateCount: selected.length,
    count: selected.length, initialWindowCandidateCount: candidates.filter(p => p.price_inr >= Math.ceil(budget * 0.9)).length,
    catalogCandidateCount: candidates.length, catalogCandidateCountLimited: pool.truncated === true,
    originalBudget: Number(originalBudget), initialPriceWindow: { min: Math.ceil(budget * 0.9), max: budget },
    priceWindow: { min: finalMin, max: budget }, finalPriceWindow: { min: finalMin, max: budget },
    matchType: selected.length ? (opts.brand ? 'within_budget_and_brand' : 'within_budget') : 'none',
    fallbackApplied: waves > 1, expansionApplied: waves > 1, livePriceWaves: waves,
    requestedBrand: opts.brand || null, partialBrandFill: false,
    brandMatchCount: opts.brand ? selected.length : 0, similarFillCount: 0,
    livePriceRefreshCompleted: true, livePriceCandidatesChecked: checked.size,
    priceVerificationStatus: selected.length ? 'verified' : 'none_verified',
    verificationFailures: rejected, stopReason, livePriceBatches: liveBatches,
    selectionElapsedMs: clock() - started, selectionPolicy: 'progressive-budget-near-v1',
  };
}

async function getTopProductsForCategoryAndBudget(category, budget, opts = {}, dependencies = {}) {
  if (category === 'smart-phones' && Number(budget) === 15000 && !String(opts.brand || '').trim()) {
    const campaign = dependencies.campaign || require('./LiveBudgetRecommendationService');
    return campaign.getTopProductsForCategoryAndBudget(category, budget, opts, dependencies);
  }
  if (Object.keys(dependencies).length) return select(category, budget, opts, dependencies);
  const key = JSON.stringify([category, Number(budget), opts.limit || 5, String(opts.brand || '').trim().toLowerCase()]);
  if (!inFlight.has(key)) {
    const task = select(category, budget, opts, dependencies).finally(() => inFlight.delete(key));
    inFlight.set(key, task);
  }
  return inFlight.get(key);
}

module.exports = { getTopProductsForCategoryAndBudget };
