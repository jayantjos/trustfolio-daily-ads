const MyProduct = require('../entities/MyProduct');
const { fromMyProduct } = require('../models/ProductSummaryDto');
const { extractPriceFromString } = require('../utils/priceUtils');
const { resolveProductPrice } = require('../utils/resolveProductPrice');
const { buildCategoryFilter, buildExactCategoryFilter } = require('../utils/categoryMongoFilter');
const { buildOemBrandFilterClause, productMatchesOemBrand } = require('../utils/brandValidation');
const { applyCategoryGuard, productHasCategoryKeywordSignals } = require('../utils/categoryGuard');
const { normalizeCategorySlugForMatch, compactCategoryKey } = require('../utils/categorySlugUtils');

/** Hyphen-agnostic canonical keys for ranker + hasCriticalSpecs (API may send smart-phones, laptops, etc.). */
const RANKING_KEY_BY_COMPACT = {
  // Phones / compute
  smartphones: 'smartphones',
  smartphone: 'smartphones',
  laptop: 'laptops',
  laptops: 'laptops',
  notebook: 'laptops',
  netbook: 'laptops',
  chromebook: 'laptops',
  tablet: 'tablets',
  tablets: 'tablets',
  ipad: 'tablets',

  // TVs
  television: 'televisions',
  televisions: 'televisions',
  tv: 'televisions',
  tvs: 'televisions',
  smarttv: 'televisions',
  smarttvs: 'televisions',

  // Headphones / earbuds (single generic rank bucket)
  earbudsheadphones: 'earbuds-headphones',
  headphonesearbuds: 'earbuds-headphones',
  headphone: 'earbuds-headphones',
  headphones: 'earbuds-headphones',
  headset: 'earbuds-headphones',
  earbud: 'earbuds-headphones',
  earbuds: 'earbuds-headphones',

  // Cooling / kitchen / climate
  refrigerator: 'refrigerators',
  refrigerators: 'refrigerators',
  fridge: 'refrigerators',
  fridges: 'refrigerators',
  airconditioner: 'air-conditioners',
  airconditioners: 'air-conditioners',
  aircooler: 'air-coolers',
  aircoolers: 'air-coolers',

  // Audio (non-wearable)
  speaker: 'speakers',
  speakers: 'speakers',
  soundbar: 'speakers',

  camera: 'cameras',
  cameras: 'cameras',
  dslr: 'cameras',

  smartwatch: 'smart-watches',
  smartwatches: 'smart-watches',

  powerbank: 'power-banks',
  powerbanks: 'power-banks',
};

/** Maps resolveRankingCategoryKey result → CATEGORY_KEYWORDS slug for productHasCategoryKeywordSignals. */
const KEYWORD_SLUG_BY_RANKING_KEY = {
  refrigerators: 'refrigerators',
  'air-conditioners': 'air-conditioners',
  'air-coolers': 'air-coolers',
  speakers: 'speakers',
  cameras: 'cameras',
  'smart-watches': 'smart-watches',
  'power-banks': 'power-banks',
  'earbuds-headphones': 'headphones',
};

function resolveRankingCategoryKey(categorySlug) {
  const normalized = normalizeCategorySlugForMatch(String(categorySlug || ''));
  if (!normalized) return null;
  const compact = compactCategoryKey(normalized);
  return RANKING_KEY_BY_COMPACT[compact] || null;
}

const RANKING_FIELDS = [
  'title',
  'brand',
  'model',
  'category',
  'platform',
  'source_platform',
  'scrapingSource',
  'currentPrice',
  'currentPriceValue',
  'price_inr',
  'priceStartRange',
  'priceEndRange',
  'list_price',
  'listPrice',
  'price',
  'exact_price',
  'exactPrice',
  'previous_price',
  'previousPrice',
  'originalPrice',
  'rating',
  'reviewCount',
  'reviews_count',
  'ratings_count',
  'key_specifications',
  'specifications',
  'image',
  'main_image',
  'image_url',
  'imageUrl',
  'thumbnail',
  'thumbnail_url',
  'thumbnailUrl',
  'images',
  'images_of_specified_asin',
  'mainImage',
  'additionalImages',
  'additional_images',
  'isBestSeller',
  'isAmazonChoice',
  'isPrime',
  'ram',
  'storage',
  'screenSize',
  'screenSizeInches',
  'display',
  'displayType',
  'processor',
  'cpuModel',
  'battery',
  'batteryLifeHours',
  'batteryLifeDays',
  'camera',
  'capacity',
  'energyRating',
  'warranty',
  'productUrl',
  'product_url',
  'clean_url',
  'scrapedAt',
].join(' ');

function getMaxRankingCandidates() {
  const parsed = parseInt(process.env.MAX_RANKING_CANDIDATES || '500', 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 500;
}

function getLegacyScanLimit() {
  const parsed = parseInt(process.env.MAX_LEGACY_SCAN_CANDIDATES || '1500', 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1500;
}

/** Upper bound on docs scanned for budget matching — align with full category used by price-bounds. */
function getBudgetWindowFetchLimit() {
  const parsed = parseInt(process.env.BUDGET_WINDOW_FETCH_LIMIT || '12000', 10);
  return Number.isFinite(parsed) && parsed > 0 ? Math.min(parsed, 25000) : 12000;
}

function getRecommendationResultLimit() {
  const parsed = parseInt(process.env.MAX_RECOMMENDATION_RESULTS || '5', 10);
  if (!Number.isFinite(parsed) || parsed <= 0) return 5;
  return Math.min(parsed, 5);
}

function getFastBudgetCandidateLimit() {
  const parsed = parseInt(process.env.FAST_BUDGET_CANDIDATE_LIMIT || '2500', 10);
  return Number.isFinite(parsed) && parsed > 0 ? Math.min(parsed, 8000) : 2500;
}

function getBudgetQueryMaxTimeMS() {
  const parsed = parseInt(process.env.BUDGET_QUERY_MAX_TIME_MS || '6000', 10);
  return Number.isFinite(parsed) && parsed >= 1000 ? parsed : 6000;
}

function buildBudgetPriceFilter(safeMin, safeMax) {
  return {
    $or: [
      { price_inr: { $gte: safeMin, $lte: safeMax } },
      { currentPriceValue: { $gte: safeMin, $lte: safeMax } },
      { priceStartRange: { $gte: safeMin, $lte: safeMax } },
      { priceEndRange: { $gte: safeMin, $lte: safeMax } },
    ],
  };
}

async function fetchCandidateBatch(filter, limit) {
  return MyProduct.find(filter)
    .select(RANKING_FIELDS)
    .limit(limit)
    .maxTimeMS(getBudgetQueryMaxTimeMS())
    .lean();
}

function filterBudgetCandidates(candidates, categorySlug, safeMin, safeMax, maxCandidates, options = {}) {
  const requestedBrand = typeof options.brand === 'string' ? options.brand.trim() : '';
  const guarded = applyCategoryGuard(candidates, categorySlug.toLowerCase());
  const filtered = [];

  for (const product of guarded) {
    if (!hasCriticalSpecs(product, categorySlug)) continue;
    const price = resolveProductPrice(product);
    if (!Number.isFinite(price) || price < safeMin || price > safeMax) continue;
    if (requestedBrand && !productMatchesOemBrand(categorySlug, product.brand, requestedBrand)) continue;
    filtered.push(product);
  }

  return {
    capped: filtered.slice(0, maxCandidates),
    totalMatches: filtered.length,
  };
}

/**
 * Price band from a lower bound up to the entered budget (never above it).
 * Default lower bound: 10% below budget (e.g. ₹15,000 → ₹13,500–₹15,000).
 *
 * Env: BUDGET_LOWER_BOUND_PCT — how far below budget the minimum price sits (default 0.10).
 */
function getBudgetLowerBoundPct() {
  const p = parseFloat(process.env.BUDGET_LOWER_BOUND_PCT || '0.10');
  if (!Number.isFinite(p) || p <= 0 || p >= 0.95) return 0.1;
  return p;
}

function getBudgetPriceWindow(budgetInINR) {
  const budgetFloor = Math.floor(budgetInINR);
  if (!Number.isFinite(budgetInINR) || budgetFloor <= 0) {
    return { min: 0, max: 0 };
  }
  const pct = getBudgetLowerBoundPct();
  const minPrice = Math.max(Math.floor(budgetInINR * (1 - pct)), 0);
  const maxPrice = budgetFloor;
  return {
    min: Math.min(minPrice, maxPrice),
    max: maxPrice,
  };
}

function normalizeCommercePlatform(product) {
  const raw = String(product.platform || product.source_platform || product.scrapingSource || '').trim().toLowerCase();
  if (!raw) return 'other';
  if (raw.includes('amazon')) return 'amazon';
  if (raw.includes('flipkart')) return 'flipkart';
  if (raw.includes('croma')) return 'croma';
  return 'other';
}

function productStableId(product) {
  if (product._id != null) return String(product._id);
  const url = product.productUrl || product.product_url || product.clean_url || '';
  return `${url}|${product.title || ''}`;
}

const INVALID_IMAGE_VALUES = new Set([
  '',
  '-',
  '--',
  'n/a',
  'na',
  'none',
  'null',
  'undefined',
  'not available',
]);

function isUsableImageValue(value) {
  if (Array.isArray(value)) return value.some(isUsableImageValue);
  const normalized = String(value ?? '').trim();
  if (!normalized) return false;
  return !INVALID_IMAGE_VALUES.has(normalized.toLowerCase());
}

function hasUsableProductImage(product) {
  return [
    product?.mainImage,
    product?.image,
    product?.main_image,
    product?.image_url,
    product?.imageUrl,
    product?.thumbnail,
    product?.thumbnail_url,
    product?.thumbnailUrl,
    product?.images,
    product?.images_of_specified_asin,
    product?.additionalImages,
    product?.additional_images,
  ].some(isUsableImageValue);
}

function pickRankedProductsWithQuotas(rankedLists, cap, quotas = []) {
  const picked = [];
  const ids = new Set();
  const cursors = rankedLists.map(() => 0);

  const takeNextFromListAtCursor = (listIdx) => {
    const list = rankedLists[listIdx] || [];
    while (cursors[listIdx] < list.length) {
      const p = list[cursors[listIdx]++];
      const id = productStableId(p);
      if (ids.has(id)) continue;
      picked.push(p);
      ids.add(id);
      return true;
    }
    return false;
  };

  quotas.forEach((quota, listIdx) => {
    let taken = 0;
    while (taken < quota && picked.length < cap) {
      if (!takeNextFromListAtCursor(listIdx)) break;
      taken += 1;
    }
  });

  while (picked.length < cap) {
    let progressed = false;
    for (let li = 0; li < rankedLists.length; li++) {
      if (picked.length >= cap) break;
      if (takeNextFromListAtCursor(li)) progressed = true;
    }
    if (!progressed) break;
  }

  return picked;
}

/**
 * Rank per platform: Amazon = rating then specs; Flipkart/Croma/other = rating when present, else specs.
 * Pick 2 Amazon + 2 Flipkart + 1 Croma first (best per platform); unfilled slots use round‑robin across
 * Amazon → Flipkart → Croma → other so mix is preserved before stacking one platform.
 */
function pickPlatformQuotaTop(categorySlug, products, resultLimit) {
  const cap = Math.min(Math.max(Number(resultLimit) || 5, 1), 5);
  const buckets = { amazon: [], flipkart: [], croma: [], other: [] };
  for (const p of products) {
    buckets[normalizeCommercePlatform(p)].push(p);
  }

  const rankAmazon = (list) => rankProductsForCategoryAndPlatform(categorySlug, list, 'amazon');
  const rankAlt = (list) => rankProductsForCategoryAndPlatform(categorySlug, list, 'flipkart');

  const rankedAmazon = rankAmazon(buckets.amazon);
  const rankedFlipkart = rankAlt(buckets.flipkart);
  const rankedCroma = rankAlt(buckets.croma);
  const rankedOther = rankAlt(buckets.other);

  const spillLists = [rankedAmazon, rankedFlipkart, rankedCroma, rankedOther];
  const imageBackedLists = spillLists.map((list) => list.filter(hasUsableProductImage));
  const picked = pickRankedProductsWithQuotas(imageBackedLists, cap, [2, 2, 1, 0]);

  if (picked.length >= cap) return picked;

  const pickedIds = new Set(picked.map(productStableId));
  const fallbackLists = spillLists.map((list) =>
    list.filter((product) => !pickedIds.has(productStableId(product)))
  );

  return [
    ...picked,
    ...pickRankedProductsWithQuotas(fallbackLists, cap - picked.length),
  ].slice(0, cap);
}

/**
 * ProductRecommendationService - matches Kotlin concept
 * Get top 5 best products for a given category and budget
 */
async function rankProductsInBudgetWindow(categorySlug, categoryProducts, totalMatches, resultLimit, minBudget, maxBudget, budgetCap, dtoOptions = {}) {
  let topRanked = pickPlatformQuotaTop(categorySlug, categoryProducts, resultLimit);
  topRanked = topRanked.filter((p) => {
    const pr = resolveProductPrice(p);
    return Number.isFinite(pr) && pr <= budgetCap && pr >= minBudget;
  });
  topRanked = orderPickedByRatingThenSpecs(categorySlug, topRanked);
  return {
    products: toProductDtos(topRanked, dtoOptions),
    totalMatches,
    priceWindow: { min: minBudget, max: maxBudget },
  };
}

async function getTopProductsForCategoryAndBudget(categorySlug, budgetInINR, options = {}) {
  const resultLimit = Number.isFinite(options.limit) && options.limit > 0
    ? Math.min(options.limit, 5)
    : getRecommendationResultLimit();
  const budgetCap = Math.floor(Number(budgetInINR));
  const excludedIds = new Set((options.excludeProductIds || []).map(String));
  const notInspected = (p) => !excludedIds.has(productStableId(p));
  const { min: minBudget, max: maxFromRule } = getBudgetPriceWindow(budgetInINR);
  const maxBudget = Number.isFinite(budgetCap) && budgetCap > 0
    ? Math.min(maxFromRule, budgetCap)
    : maxFromRule;

  const requestedBrand = typeof options.brand === 'string' ? options.brand.trim() : '';
  const preferredWindow = { min: minBudget, max: maxBudget };
  const emptyResult = {
    products: [],
    totalMatches: 0,
    matchType: 'none',
    priceWindow: preferredWindow,
    fallbackApplied: false,
    requestedBrand: requestedBrand || null,
  };

  if (requestedBrand) {
    const withBrand = await loadBudgetCandidates(
      categorySlug, minBudget, maxBudget, budgetCap, { brand: requestedBrand, excludeProductIds: [...excludedIds] }
    );
    const brandFiltered = withBrand.capped.filter((p) =>
      notInspected(p) && productMatchesOemBrand(categorySlug, p.brand, requestedBrand)
    );
    if (brandFiltered.length > 0) {
      const brandRaw = rankRawProductsInBudgetWindow(
        categorySlug, brandFiltered, resultLimit, withBrand.windowMin, withBrand.windowMax, budgetCap
      );
      const slotsRemaining = resultLimit - brandRaw.length;

      if (slotsRemaining > 0) {
        const withoutBrand = await loadBudgetCandidates(
          categorySlug, withBrand.windowMin, withBrand.windowMax, budgetCap, { excludeProductIds: [...excludedIds] }
        );
        const pickedIds = new Set(brandRaw.map(productStableId));
        const similarPool = withoutBrand.capped.filter(
          (p) =>
            !pickedIds.has(productStableId(p)) &&
            notInspected(p) &&
            !productMatchesOemBrand(categorySlug, p.brand, requestedBrand)
        );
        const similarRaw = rankRawProductsInBudgetWindow(
          categorySlug, similarPool, slotsRemaining, withoutBrand.windowMin, withoutBrand.windowMax, budgetCap
        );
        const combined = [...brandRaw, ...similarRaw];
        return {
          products: toProductDtos(combined, { categorySlug, requestedBrand }),
          totalMatches: brandFiltered.length,
          priceWindow: { min: withBrand.windowMin, max: withBrand.windowMax },
          matchType: 'within_budget_and_brand_partial',
          fallbackApplied: true,
          partialBrandFill: true,
          brandMatchCount: brandRaw.length,
          similarFillCount: similarRaw.length,
          requestedBrand,
        };
      }

      return {
        products: toProductDtos(brandRaw, { categorySlug, requestedBrand }),
        totalMatches: brandFiltered.length,
        priceWindow: { min: withBrand.windowMin, max: withBrand.windowMax },
        matchType: 'within_budget_and_brand',
        fallbackApplied: false,
        partialBrandFill: false,
        brandMatchCount: brandRaw.length,
        similarFillCount: 0,
        requestedBrand,
      };
    }

    const withoutBrand = await loadBudgetCandidates(
      categorySlug, minBudget, maxBudget, budgetCap, { excludeProductIds: [...excludedIds] }
    );
    if (withoutBrand.capped.length > 0) {
      const ranked = await rankProductsInBudgetWindow(
        categorySlug, withoutBrand.capped.filter(notInspected), withoutBrand.totalMatches,
        resultLimit, withoutBrand.windowMin, withoutBrand.windowMax, budgetCap,
        { categorySlug, requestedBrand }
      );
      return {
        ...ranked,
        priceWindow: { min: withoutBrand.windowMin, max: withoutBrand.windowMax },
        matchType: 'within_budget_brand_fallback',
        fallbackApplied: true,
        requestedBrand,
      };
    }
    return emptyResult;
  }

  const loaded = await loadBudgetCandidates(
    categorySlug, minBudget, maxBudget, budgetCap, { excludeProductIds: [...excludedIds] }
  );
  if (loaded.capped.length > 0) {
    const ranked = await rankProductsInBudgetWindow(
      categorySlug, loaded.capped.filter(notInspected), loaded.totalMatches,
      resultLimit, loaded.windowMin, loaded.windowMax, budgetCap
    );
    return {
      ...ranked,
      priceWindow: { min: loaded.windowMin, max: loaded.windowMax },
      matchType: 'within_budget',
      fallbackApplied: false,
      requestedBrand: null,
    };
  }
  return emptyResult;
}

/**
 * Prefer the near-budget band (e.g. 10% below the entered amount). If that band
 * is empty, widen to every in-category product at or below the entered budget
 * so a catalog min of ₹16,999 is not skipped for a ₹22,000 search.
 */
async function loadBudgetCandidates(categorySlug, minBudget, maxBudget, budgetCap, options = {}) {
  const primary = await fetchProductsInBudgetWindow(
    categorySlug, minBudget, maxBudget, budgetCap, options
  );
  const excluded = new Set((options.excludeProductIds || []).map(String));
  const hasUninspected = primary.capped.some((p) => !excluded.has(productStableId(p)));
  if (hasUninspected || minBudget <= 0) {
    return {
      ...primary,
      windowMin: Math.max(0, Math.floor(minBudget)),
      windowMax: Math.floor(maxBudget),
      expandedWindow: false,
    };
  }

  const expanded = await fetchProductsInBudgetWindow(
    categorySlug, 0, budgetCap, budgetCap, options
  );
  return {
    ...expanded,
    windowMin: 0,
    windowMax: budgetCap,
    expandedWindow: expanded.capped.length > 0,
  };
}

function appendBrandToFilterParts(parts, brandName, categorySlug) {
  const brandClause = buildOemBrandFilterClause(categorySlug, brandName);
  if (!brandClause) return parts;
  return [...parts, brandClause];
}

async function fetchProductsInBudgetWindow(categorySlug, minBudgetInINR, maxBudgetInINR, budgetHardCap, options = {}) {
  const brandName = typeof options.brand === 'string' ? options.brand.trim() : '';
  const safeMin = Math.floor(minBudgetInINR);
  let safeMax = Math.floor(maxBudgetInINR);
  if (!Number.isFinite(safeMax) || safeMax <= 0) {
    return { capped: [], totalMatches: 0 };
  }
  if (Number.isFinite(budgetHardCap) && budgetHardCap > 0) {
    safeMax = Math.min(safeMax, Math.floor(budgetHardCap));
  }
  if (!Number.isFinite(safeMin) || safeMin > safeMax) {
    return { capped: [], totalMatches: 0 };
  }

  const maxCandidates = getMaxRankingCandidates();
  const scanCap = Math.max(getBudgetWindowFetchLimit(), getLegacyScanLimit());

  const categoryFilter = buildCategoryFilter(categorySlug);
  if (!categoryFilter) {
    return { capped: [], totalMatches: 0 };
  }
  const exactCategoryFilter = buildExactCategoryFilter(categorySlug);

  const activeClause = {
    $or: [
      { isActive: true },
      { isActive: { $exists: false } },
      { isActive: null },
    ],
  };

  const priceFilter = buildBudgetPriceFilter(safeMin, safeMax);
  const filterOpts = brandName ? { brand: brandName } : {};
  // FAST_TOP_PRODUCTS_INDEXED_SLUG_PRICE_V1
  // First try exact category_slug + numeric price fields, using compound indexes.
  // Skip when brand filter is active — fast path does not apply OEM brand clauses.
  const directSlug = normalizeCategorySlugForMatch(categorySlug);
  if (directSlug && !brandName) {
    // FAST_TOP_DIRECT_LIMIT_V1: keep first API response light; fallback still exists below.
    const configuredDirectLimit = parseInt(process.env.FAST_TOP_DIRECT_LIMIT || '300', 10);
    const directLimit = Math.min(
      getFastBudgetCandidateLimit(),
      Number.isFinite(configuredDirectLimit) && configuredDirectLimit > 0 ? configuredDirectLimit : 300
    );
    const directPlans = [
      {
        name: 'category_slug_price_inr',
        filter: {
          $and: [
            activeClause,
            { category_slug: directSlug },
            { price_inr: { $gte: safeMin, $lte: safeMax } },
          ],
        },
        sort: { price_inr: -1 },
      },
      {
        name: 'category_slug_currentPriceValue',
        filter: {
          $and: [
            activeClause,
            { category_slug: directSlug },
            { currentPriceValue: { $gte: safeMin, $lte: safeMax } },
          ],
        },
        sort: { currentPriceValue: -1 },
      },
    ];

    for (const directPlan of directPlans) {
      try {
        const candidates = await MyProduct.find(directPlan.filter)
          .select(RANKING_FIELDS)
          .sort(directPlan.sort)
          .limit(directLimit)
          .maxTimeMS(getBudgetQueryMaxTimeMS())
          .lean();

        const result = filterBudgetCandidates(
          candidates, categorySlug, safeMin, safeMax, maxCandidates, filterOpts
        );
        if (result.totalMatches > 0) {
          return result;
        }
      } catch (error) {
        console.warn('[Recommendation] Indexed fast path skipped:', directPlan.name, error.message || error);
      }
    }
  }

  const fastLimit = Math.min(scanCap, getFastBudgetCandidateLimit());
  const fallbackLimit = Math.min(scanCap, getLegacyScanLimit());
  const queryPlans = [];

  if (exactCategoryFilter) {
    queryPlans.push({
      filter: { $and: appendBrandToFilterParts([activeClause, exactCategoryFilter, priceFilter], brandName, categorySlug) },
      limit: fastLimit,
    });
    if (!brandName) {
      queryPlans.push({ filter: { $and: [activeClause, exactCategoryFilter] }, limit: fallbackLimit });
    }
  }
  queryPlans.push({
    filter: { $and: appendBrandToFilterParts([activeClause, categoryFilter, priceFilter], brandName, categorySlug) },
    limit: fastLimit,
  });
  if (!brandName) {
    queryPlans.push({ filter: { $and: [activeClause, categoryFilter] }, limit: fallbackLimit });
  }

  const seenPlans = new Set();
  for (const plan of queryPlans) {
    const planKey = JSON.stringify(plan.filter);
    if (seenPlans.has(planKey)) continue;
    seenPlans.add(planKey);

    try {
      const candidates = await fetchCandidateBatch(plan.filter, plan.limit);
      const result = filterBudgetCandidates(
        candidates, categorySlug, safeMin, safeMax, maxCandidates, filterOpts
      );
      if (result.totalMatches > 0) return result;
    } catch (error) {
      console.warn('[Recommendation] Candidate query skipped:', error.message || error);
    }
  }

  return { capped: [], totalMatches: 0 };
}

async function getProductsInBudgetWindow(categorySlug, minBudgetInINR, maxBudgetInINR, budgetHardCap) {
  const { capped } = await fetchProductsInBudgetWindow(categorySlug, minBudgetInINR, maxBudgetInINR, budgetHardCap);
  return capped;
}

function hasCriticalSpecs(product, categorySlug) {
  const key = resolveRankingCategoryKey(categorySlug);
  const title = String(product.title || '');
  if (key === 'smartphones' || key === 'laptops' || key === 'tablets') {
    const hasRam = product.ram || /(\d+)\s*GB\s*RAM/i.test(title);
    const hasStorage = product.storage || /(\d+(?:\.\d+)?)\s*(TB|GB)\s*(?:SSD|HDD|ROM|Storage|Internal)?/i.test(title);
    if (hasRam || hasStorage) return true;
    return Boolean(
      product.processor
      || product.cpuModel
      || product.display
      || product.screenSize
      || product.battery
      || title.trim().length > 0
    );
  }
  if (key === 'televisions') {
    return product.screenSize || product.screenSizeInches || product.display || /tv|television|qled|oled|led/i.test(title);
  }

  const kwSlug = key && KEYWORD_SLUG_BY_RANKING_KEY[key];
  if (kwSlug) {
    if (productHasCategoryKeywordSignals(product, kwSlug)) return true;
    return title.trim().length > 0;
  }

  return Boolean(product.ram || product.storage || product.battery || product.screenSize || title.trim());
}

function toProductDtos(products, options = {}) {
  const { categorySlug, requestedBrand } = options;
  return products.map((product, index) => {
    const priceInINR = resolveProductPrice(product);
    const originalPriceInINR = product.originalPrice ? extractPriceFromString(product.originalPrice) : null;
    const dto = fromMyProduct(product, priceInINR, originalPriceInINR);
    const row = { ...dto, rank: index + 1 };
    if (requestedBrand && categorySlug) {
      row.isRequestedBrandMatch = productMatchesOemBrand(categorySlug, product.brand, requestedBrand);
    }
    return row;
  });
}

function rankRawProductsInBudgetWindow(categorySlug, categoryProducts, resultLimit, minBudget, maxBudget, budgetCap) {
  let topRanked = pickPlatformQuotaTop(categorySlug, categoryProducts, resultLimit);
  topRanked = topRanked.filter((p) => {
    const pr = resolveProductPrice(p);
    return Number.isFinite(pr) && pr <= budgetCap && pr >= minBudget;
  });
  return orderPickedByRatingThenSpecs(categorySlug, topRanked);
}

function rankProductsForCategoryAndPlatform(categorySlug, products, platformKind) {
  const amazonStyle = platformKind === 'amazon';
  const key = resolveRankingCategoryKey(categorySlug);
  if (key === 'smartphones') return amazonStyle ? rankSmartphones(products) : rankSmartphonesAltPlatforms(products);
  if (key === 'laptops') return amazonStyle ? rankLaptopsAmazonFirst(products) : rankLaptopsAltPlatforms(products);
  if (key === 'televisions') return amazonStyle ? rankTelevisionsAmazonFirst(products) : rankTelevisionsAltPlatforms(products);
  if (key === 'earbuds-headphones') return amazonStyle ? rankGenericAmazonFirst(products) : rankGenericAltPlatforms(products);
  return amazonStyle ? rankGenericAmazonFirst(products) : rankGenericAltPlatforms(products);
}

function extractNumericFromSpec(spec) {
  if (!spec) return 0;
  const m = String(spec).match(/(\d+)/);
  return m ? parseInt(m[1], 10) : 0;
}

function toPlainObjectDoc(value) {
  if (value != null && typeof value === 'object' && !Array.isArray(value)) return value;
  return null;
}

/** RAM in GB from fields, title, key_specifications, or specifications (Croma/Flipkart shapes). */
function extractSmartphoneRamGb(product) {
  let ram = extractNumericFromSpec(product.ram);
  if (ram > 0) return ram;
  const title = String(product.title || '');
  const tm = title.match(/(\d+)\s*GB\s*RAM/i);
  if (tm) return parseInt(tm[1], 10);
  if (Array.isArray(product.key_specifications)) {
    for (const line of product.key_specifications) {
      const m = String(line).match(/(\d+)\s*GB\s*RAM/i);
      if (m) return parseInt(m[1], 10);
    }
  }
  const specs = toPlainObjectDoc(product.specifications);
  if (specs) {
    const direct = specs.RAM ?? specs.ram;
    ram = extractNumericFromSpec(direct);
    if (ram > 0) return ram;
    for (const [k, v] of Object.entries(specs)) {
      if (!/ram|memory/i.test(String(k))) continue;
      ram = extractNumericFromSpec(v);
      if (ram > 0) return ram;
    }
  }
  return 0;
}

/**
 * Storage in GB (best effort). Skips GB adjacent to "RAM" in title; parses TB.
 */
function extractSmartphoneStorageGb(product) {
  let maxGb = 0;
  const bump = (n) => {
    if (Number.isFinite(n) && n > maxGb) maxGb = n;
  };

  bump(extractNumericFromSpec(product.storage));

  const title = String(product.title || '');
  const afterRamComma = title.match(/RAM\s*,\s*(\d+(?:\.\d+)?)\s*(TB|GB)/i);
  if (afterRamComma) {
    const val = parseFloat(afterRamComma[1]);
    const u = String(afterRamComma[2] || '').toUpperCase();
    bump(u === 'TB' ? val * 1024 : val);
  }

  for (const m of title.matchAll(/(\d+(?:\.\d+)?)\s*(TB|GB)/gi)) {
    const start = Math.max(0, m.index - 20);
    const snippet = title.slice(start, m.index + m[0].length + 8);
    if (/RAM/i.test(snippet) && !/(Storage|ROM|Internal)/i.test(snippet)) continue;
    const val = parseFloat(m[1]);
    const u = String(m[2] || '').toUpperCase();
    const gb = u === 'TB' ? val * 1024 : val;
    if (gb >= 16) bump(gb);
  }

  if (Array.isArray(product.key_specifications)) {
    for (const line of product.key_specifications) {
      const s = String(line);
      if (/RAM/i.test(s) && !/(Storage|ROM)/i.test(s)) continue;
      const mm = s.match(/(\d+(?:\.\d+)?)\s*(TB|GB)/i);
      if (mm) {
        const val = parseFloat(mm[1]);
        const u = String(mm[2] || '').toUpperCase();
        bump(u === 'TB' ? val * 1024 : val);
      }
    }
  }

  const specs = toPlainObjectDoc(product.specifications);
  if (specs) {
    for (const k of ['Storage', 'storage', 'ROM', 'Internal Storage', 'internal_storage']) {
      if (specs[k] == null) continue;
      bump(extractNumericFromSpec(specs[k]));
    }
  }

  return maxGb;
}

function extractRating(product) {
  const r = parseFloat(product.rating);
  return r > 0 ? r : null;
}

function extractReviewCount(product) {
  const text = product.reviewCount || product.reviews_count || product.ratings_count || '';
  const m = String(text).match(/[\d,]+/);
  return m ? parseInt(m[0].replace(/,/g, ''), 10) : 0;
}

function extractScreenSize(title) {
  const m = String(title || '').match(/(\d+)\s*(?:inch|")/i);
  return m ? parseInt(m[1], 10) : 0;
}

/** RAM + storage tiers only (no rating); uses same extraction as sort for Croma etc. */
function smartphoneSpecScore(product) {
  let score = 0;
  const ram = extractSmartphoneRamGb(product);
  if (ram >= 12) score += 30;
  else if (ram >= 8) score += 24;
  else if (ram >= 6) score += 18;
  else score += 10;
  const storage = extractSmartphoneStorageGb(product);
  if (storage >= 256) score += 20;
  else if (storage >= 128) score += 16;
  else score += 8;
  return score;
}

/**
 * After platform quotas pick the set of products, order that set for API/UI:
 * highest rating first; ties broken by category-specific specs (same logic as per-platform rank).
 */
function orderPickedByRatingThenSpecs(categorySlug, products) {
  const key = resolveRankingCategoryKey(categorySlug);
  if (key === 'smartphones') return [...products].sort(compareSmartphonesRatingThenSpecs);
  if (key === 'laptops') return [...products].sort(compareLaptopsRatingThenSpecs);
  if (key === 'televisions') return [...products].sort(compareTelevisionsRatingThenSpecs);
  if (key === 'earbuds-headphones') return [...products].sort(compareGenericRatingThenSpecs);
  return [...products].sort(compareGenericRatingThenSpecs);
}

function compareSmartphonesRatingThenSpecs(a, b) {
  const ratingA = extractRating(a) ?? 0;
  const ratingB = extractRating(b) ?? 0;
  if (ratingB !== ratingA) return ratingB - ratingA;

  const storageA = extractSmartphoneStorageGb(a);
  const storageB = extractSmartphoneStorageGb(b);
  if (storageB !== storageA) return storageB - storageA;

  const ramA = extractSmartphoneRamGb(a);
  const ramB = extractSmartphoneRamGb(b);
  if (ramB !== ramA) return ramB - ramA;

  const specA = smartphoneSpecScore(a);
  const specB = smartphoneSpecScore(b);
  if (specB !== specA) return specB - specA;

  return extractReviewCount(b) - extractReviewCount(a);
}

function rankSmartphones(products) {
  return [...products].sort(compareSmartphonesRatingThenSpecs);
}

/** Flipkart / Croma / other: rating when present; if missing, order by specifications. */
function rankSmartphonesAltPlatforms(products) {
  return [...products].sort((a, b) => {
    const ra = extractRating(a);
    const rb = extractRating(b);
    const ha = ra != null && ra > 0;
    const hb = rb != null && rb > 0;
    if (ha && hb && ra !== rb) return rb - ra;
    if (ha && !hb) return -1;
    if (!ha && hb) return 1;

    const storageA = extractSmartphoneStorageGb(a);
    const storageB = extractSmartphoneStorageGb(b);
    if (storageB !== storageA) return storageB - storageA;

    const ramA = extractSmartphoneRamGb(a);
    const ramB = extractSmartphoneRamGb(b);
    if (ramB !== ramA) return ramB - ramA;

    const specA = smartphoneSpecScore(a);
    const specB = smartphoneSpecScore(b);
    if (specB !== specA) return specB - specA;

    return extractReviewCount(b) - extractReviewCount(a);
  });
}

function compareLaptopsSpecOnly(a, b) {
  let scoreA = 0;
  let scoreB = 0;
  const ramA = extractNumericFromSpec(a.ram);
  const ramB = extractNumericFromSpec(b.ram);
  if (ramA >= 16) scoreA += 28; else if (ramA >= 8) scoreA += 16; else scoreA += 8;
  if (ramB >= 16) scoreB += 28; else if (ramB >= 8) scoreB += 16; else scoreB += 8;
  if (/i7|Ryzen 7/i.test(a.processor || '') || /i7|Ryzen 7/i.test(a.cpuModel || '')) scoreA += 16;
  if (/i5|Ryzen 5/i.test(a.processor || '') || /i5|Ryzen 5/i.test(a.cpuModel || '')) scoreA += 12;
  if (/i7|Ryzen 7/i.test(b.processor || '') || /i7|Ryzen 7/i.test(b.cpuModel || '')) scoreB += 16;
  if (/i5|Ryzen 5/i.test(b.processor || '') || /i5|Ryzen 5/i.test(b.cpuModel || '')) scoreB += 12;
  return scoreB - scoreA;
}

function compareLaptopsRatingThenSpecs(a, b) {
  const ra = extractRating(a) || 0;
  const rb = extractRating(b) || 0;
  if (rb !== ra) return rb - ra;
  return compareLaptopsSpecOnly(a, b);
}

function rankLaptopsAmazonFirst(products) {
  return [...products].sort(compareLaptopsRatingThenSpecs);
}

function rankLaptopsAltPlatforms(products) {
  return [...products].sort((a, b) => {
    const ra = extractRating(a);
    const rb = extractRating(b);
    const ha = ra != null && ra > 0;
    const hb = rb != null && rb > 0;
    if (ha && hb && ra !== rb) return rb - ra;
    if (ha && !hb) return -1;
    if (!ha && hb) return 1;
    return compareLaptopsSpecOnly(a, b);
  });
}

function televisionSpecScore(product) {
  let score = 0;
  const title = product.title || '';
  if (/OLED/i.test(title)) score += 30; else if (/4K/i.test(title)) score += 20; else score += 10;
  const size = extractScreenSize(title);
  score += size >= 55 ? 15 : size >= 43 ? 12 : 8;
  return score;
}

function compareTelevisionsRatingThenSpecs(a, b) {
  const ra = extractRating(a) || 0;
  const rb = extractRating(b) || 0;
  if (rb !== ra) return rb - ra;
  return televisionSpecScore(b) - televisionSpecScore(a);
}

function rankTelevisionsAmazonFirst(products) {
  return [...products].sort(compareTelevisionsRatingThenSpecs);
}

function rankTelevisionsAltPlatforms(products) {
  return [...products].sort((a, b) => {
    const ra = extractRating(a);
    const rb = extractRating(b);
    const ha = ra != null && ra > 0;
    const hb = rb != null && rb > 0;
    if (ha && hb && ra !== rb) return rb - ra;
    if (ha && !hb) return -1;
    if (!ha && hb) return 1;
    return televisionSpecScore(b) - televisionSpecScore(a);
  });
}

function genericEngagementScore(product) {
  let score = 0;
  const revA = extractReviewCount(product);
  score += revA >= 1000 ? 25 : revA >= 500 ? 20 : 10;
  if (product.isBestSeller) score += 5;
  if (product.isAmazonChoice) score += 4;
  if (product.isPrime) score += 6;
  return score;
}

function compareGenericRatingThenSpecs(a, b) {
  const ra = extractRating(a) || 0;
  const rb = extractRating(b) || 0;
  if (rb !== ra) return rb - ra;
  return genericEngagementScore(b) - genericEngagementScore(a);
}

function rankGenericAmazonFirst(products) {
  return [...products].sort(compareGenericRatingThenSpecs);
}

function rankGenericAltPlatforms(products) {
  return [...products].sort((a, b) => {
    const ra = extractRating(a);
    const rb = extractRating(b);
    const ha = ra != null && ra > 0;
    const hb = rb != null && rb > 0;
    if (ha && hb && ra !== rb) return rb - ra;
    if (ha && !hb) return -1;
    if (!ha && hb) return 1;
    return genericEngagementScore(b) - genericEngagementScore(a);
  });
}

module.exports = {
  getTopProductsForCategoryAndBudget,
  getProductsInBudgetWindow,
  hasCriticalSpecs,
  extractPriceFromString,
};
