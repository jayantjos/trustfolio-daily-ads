const mongoose = require('mongoose');
const MyProduct = require('../entities/MyProduct');
const Product = require('../entities/Product');
const Category = require('../entities/Category');
const { apiResponse } = require('../utils/apiResponse');
const { fromMyProduct } = require('../models/ProductSummaryDto');
const { extractPriceFromString } = require('../utils/priceUtils');
const { resolveProductPrice } = require('../utils/resolveProductPrice');
const { getCanonicalPriceBounds } = require('../utils/productPriceBounds');
const { normalizeCategorySlugForMatch, getCategoryProductNouns } = require('../utils/categorySlugUtils');
const { escapeRegex, buildCategoryFilter, buildExactCategoryFilter } = require('../utils/categoryMongoFilter');
const { applyCategoryGuard } = require('../utils/categoryGuard');
const ProductRecommendationService = require('../services/ProductRecommendationService');
const LiveBudgetRecommendationService = require('../services/LiveBudgetRecommendationService');
const BrandService = require('../services/BrandService');
const { isValidBrandParam } = require('../utils/brandUtils');

function extractPrice(priceText) {
  return extractPriceFromString(priceText);
}

/** Same [min,max] envelope as GET /products/price-bounds, intersected with query min/max. */
function resolveEffectiveCategoryPriceRange(normalizedCategory, guardedProducts, min_price, max_price) {
  if (!normalizedCategory || !guardedProducts.length) {
    return { effMin: min_price ?? null, effMax: max_price ?? null };
  }
  const canonical = getCanonicalPriceBounds(guardedProducts);
  if (!canonical || canonical.count === 0) {
    return { effMin: min_price ?? null, effMax: max_price ?? null };
  }
  let effMin = canonical.min;
  let effMax = canonical.max;
  if (min_price != null) effMin = Math.max(min_price, canonical.min);
  if (max_price != null) effMax = Math.min(max_price, canonical.max);
  if (effMin > effMax) effMax = effMin;
  return { effMin, effMax };
}

function priceMatchesEffectiveRange(price, effMin, effMax) {
  if (!Number.isFinite(price) || price <= 0) return false;
  if (effMin == null && effMax == null) return true;
  if (effMin != null && price < effMin) return false;
  if (effMax != null && price > effMax) return false;
  return true;
}

function dbConnected() {
  return mongoose.connection.readyState === 1;
}

const ACTIVE_PRODUCT_CLAUSE = {
  $or: [
    { isActive: true },
    { isActive: { $exists: false } },
    { isActive: null },
  ],
};

const PRICE_BOUNDS_PROJECTION = {
  currentPrice: 1,
  currentPriceValue: 1,
  originalPrice: 1,
  priceStartRange: 1,
  priceEndRange: 1,
  price_inr: 1,
  title: 1,
  category: 1,
  product_category: 1,
  category_slug: 1,
  list_price: 1,
  listPrice: 1,
  price: 1,
  exact_price: 1,
  exactPrice: 1,
  previous_price: 1,
  previousPrice: 1,
};

const livePriceBoundsCache = new Map();

// TOP_PRODUCTS_RESPONSE_CACHE_V1
// Mobile app may repeat same category/budget request; cache short-lived final response.
const topProductsResponseCache = new Map();

function topProductsResponseCacheTtlMs() {
  const parsed = parseInt(process.env.TOP_PRODUCTS_RESPONSE_CACHE_TTL_MS || '600000', 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 600000;
}

/** Bump when bounds logic changes so TTL cache cannot return pre-change min/max. */
const PRICE_BOUNDS_CACHE_REVISION = 'cat-guard-v2';

function livePriceBoundsCacheTtlMs() {
  const n = parseInt(process.env.PRICE_BOUNDS_CACHE_TTL_MS || '60000', 10);
  return Number.isFinite(n) && n >= 0 ? n : 60000;
}

/**
 * Load products used for min/max price envelope. Prefer exact category $in (smaller, index-friendly);
 * fall back to broad regex filter only when the guarded exact set is empty.
 */
async function loadProductsForCanonicalPriceBounds(categoryRaw) {
  const category = String(categoryRaw || '').trim();
  const normalizedLower = category ? category.toLowerCase() : '';

  if (!category) {
    return MyProduct.find(ACTIVE_PRODUCT_CLAUSE, PRICE_BOUNDS_PROJECTION).lean();
  }

  const exact = buildExactCategoryFilter(category);
  const broad = buildCategoryFilter(category);
  const runFind = async (catFilter) =>
    MyProduct.find({ $and: [ACTIVE_PRODUCT_CLAUSE, catFilter] }, PRICE_BOUNDS_PROJECTION).lean();

  let usedExact = false;
  let catFilter = broad;
  if (exact) {
    catFilter = exact;
    usedExact = true;
  }

  let products = await runFind(catFilter);
  products = applyCategoryGuard(products, normalizedLower);

  if (products.length === 0 && usedExact && broad) {
    products = await runFind(broad);
    products = applyCategoryGuard(products, normalizedLower);
  }

  return products;
}

async function getProducts(req, res) {
  try {
    if (!dbConnected()) {
      return res.json(
        apiResponse(true, 'Products retrieved successfully', {
          products: [],
          currentPage: 0,
          totalPages: 0,
          totalElements: 0,
          hasNext: false,
          hasPrevious: false,
        })
      );
    }
    const page = parseInt(req.query.page, 10) || 0;
    const limit = Math.min(parseInt(req.query.limit, 10) || 20, 100);
    const category = req.query.category;
    const normalizedCategory = category ? String(category).trim().toLowerCase() : '';
    const search = typeof req.query.search === 'string' ? req.query.search.trim() : '';
    const brand = req.query.brand;
    const min_price = req.query.min_price ? parseFloat(req.query.min_price) : null;
    const max_price = req.query.max_price ? parseFloat(req.query.max_price) : null;
    const hasIsActiveParam = req.query.is_active !== undefined;
    const is_active = hasIsActiveParam ? req.query.is_active === 'true' : null;
    const sort_by = req.query.sort_by || 'created_at_desc';

    const filter = {};
    if (is_active !== null) filter.isActive = is_active;
    const exactCategoryFilter = buildExactCategoryFilter(category);
    const categoryFilter = exactCategoryFilter || buildCategoryFilter(category);
    if (categoryFilter) {
      filter.$and = filter.$and || [];
      filter.$and.push(categoryFilter);
    }
    if (brand) filter.brand = new RegExp(brand, 'i');
    if (search) {
      filter.$text = { $search: search };
    }

    const projection = search ? { score: { $meta: 'textScore' } } : undefined;

    let totalElements = await MyProduct.countDocuments(filter);
    const needsPriceSort = sort_by === 'price_asc' || sort_by === 'price_desc';
    const dir = sort_by === 'price_desc' ? -1 : 1; // default asc

    if (needsPriceSort) {
      let allProducts = await MyProduct.find(filter, projection).lean();

      if (normalizedCategory) {
        allProducts = applyCategoryGuard(allProducts, normalizedCategory);
      }

      const range = resolveEffectiveCategoryPriceRange(
        normalizedCategory,
        normalizedCategory ? allProducts : [],
        min_price,
        max_price
      );

      const withPrice = allProducts
        .map((product) => {
          const price = resolveProductPrice(product);
          return { product, price };
        })
        .filter(({ price }) => priceMatchesEffectiveRange(price, range.effMin, range.effMax));

      withPrice.sort((a, b) => (dir === 1 ? a.price - b.price : b.price - a.price));

      const paged = withPrice.slice(page * limit, page * limit + limit);
      const productDtos = paged.map(({ product, price }) => {
        const originalPriceInINR = extractPrice(product.originalPrice);
        return fromMyProduct(product, price, originalPriceInINR);
      });

      totalElements = withPrice.length;
      const totalPages = limit > 0 ? Math.ceil(withPrice.length / limit) : 1;
      return res.json(
        apiResponse(true, 'Products retrieved successfully', {
          products: productDtos,
          currentPage: page,
          totalPages,
          totalElements,
          hasNext: page < totalPages - 1,
          hasPrevious: page > 0,
        })
      );
    }

    // Non-price sorts
    let sort = { scrapedAt: -1 };
    if (search) {
      sort = { score: { $meta: 'textScore' }, scrapedAt: -1 };
    } else if (sort_by === 'rating_desc') sort = { starRating: -1 };
    else if (sort_by === 'title_asc') sort = { title: 1 };

    const baseQuery = MyProduct.find(filter, projection).sort(sort);
    let products;

    const shouldApplyPriceClip = min_price != null || max_price != null;

    if (normalizedCategory && !shouldApplyPriceClip) {
      // Fast path for normal category listing:
      // apply pagination in MongoDB instead of loading the full category in Node.js.
      products = await baseQuery.skip(page * limit).limit(limit).lean();
      products = applyCategoryGuard(products, normalizedCategory);
      totalElements = await MyProduct.countDocuments(filter);
    } else if (normalizedCategory) {
      // Keep old full-category behavior only when explicit price filters are used.
      products = await baseQuery.lean();
      products = applyCategoryGuard(products, normalizedCategory);

      const range = resolveEffectiveCategoryPriceRange(
        normalizedCategory,
        products,
        min_price,
        max_price
      );

      products = products.filter((product) =>
        priceMatchesEffectiveRange(resolveProductPrice(product), range.effMin, range.effMax)
      );

      totalElements = products.length;
      products = products.slice(page * limit, page * limit + limit);
    } else {
      products = await baseQuery.skip(page * limit).limit(limit).lean();

      if (shouldApplyPriceClip) {
        const range = resolveEffectiveCategoryPriceRange(
          normalizedCategory,
          [],
          min_price,
          max_price
        );

        products = products.filter((product) =>
          priceMatchesEffectiveRange(resolveProductPrice(product), range.effMin, range.effMax)
        );
      }
    }

    const productDtos = products.map((product) => {
      const priceInINR = resolveProductPrice(product);
      const originalPriceInINR = extractPrice(product.originalPrice);
      return fromMyProduct(product, priceInINR, originalPriceInINR);
    });

    const totalPages = limit > 0 ? Math.ceil(totalElements / limit) : 1;
    res.json(
      apiResponse(true, 'Products retrieved successfully', {
        products: productDtos,
        currentPage: page,
        totalPages,
        totalElements,
        hasNext: page < totalPages - 1,
        hasPrevious: page > 0,
      })
    );
  } catch (e) {
    res.status(400).json(apiResponse(false, `Failed to retrieve products: ${e.message}`));
  }
}

async function getProductCount(req, res) {
  try {
    if (!dbConnected()) {
      return res.json(apiResponse(true, 'Product count retrieved successfully', {
        totalProducts: 0,
        activeProducts: 0,
        categoryCounts: [],
      }));
    }
    const totalProducts = await MyProduct.countDocuments();
    const activeProducts = await MyProduct.countDocuments({
      $or: [{ isActive: true }, { isActive: { $exists: false } }, { isActive: null }],
    });

    // Aggregate counts by category (active products only). Group keys are lowercased raw
    // category|product_category — merge with normalize so "smart phones" and "smart-phones" sum for the same card.
    const categoryCountsAgg = await MyProduct.aggregate([
      {
        $match: {
          $or: [{ isActive: true }, { isActive: { $exists: false } }, { isActive: null }],
        },
      },
      {
        $group: {
          _id: {
            $toLower: {
              $ifNull: ['$category', { $ifNull: ['$product_category', 'uncategorized'] }],
            },
          },
          count: { $sum: 1 },
        },
      },
      { $sort: { count: -1 } },
    ]);

    const mergedBySlug = new Map();
    for (const doc of categoryCountsAgg) {
      const raw = doc._id;
      const c = doc.count || 0;
      if (raw == null || String(raw).trim() === '' || raw === 'uncategorized') {
        mergedBySlug.set('uncategorized', (mergedBySlug.get('uncategorized') || 0) + c);
        continue;
      }
      const key = normalizeCategorySlugForMatch(String(raw));
      if (!key) {
        mergedBySlug.set('uncategorized', (mergedBySlug.get('uncategorized') || 0) + c);
        continue;
      }
      mergedBySlug.set(key, (mergedBySlug.get(key) || 0) + c);
    }
    const categoryCounts = [...mergedBySlug.entries()]
      .map(([category, count]) => ({ category, count }))
      .sort((a, b) => b.count - a.count);

    res.json(
      apiResponse(true, 'Product count retrieved successfully', {
        totalProducts,
        activeProducts,
        categoryCounts,
      })
    );
  } catch (e) {
    res.status(400).json(apiResponse(false, `Failed to retrieve product count: ${e.message}`));
  }
}

async function getProductByAsin(req, res) {
  try {
    if (!dbConnected()) {
      return res.json(apiResponse(true, 'Product not found', null));
    }
    const asinInput = String(req.params.asin || '').trim();
    if (!asinInput || asinInput.length > 120) {
      return res.status(400).json(apiResponse(false, 'Invalid ASIN'));
    }

    const asinUpper = asinInput.toUpperCase();
    const or = [
      { asin: asinUpper },
      { asin: asinInput },
      { productUrl: new RegExp(`/dp/${escapeRegex(asinUpper)}`, 'i') },
    ];

    if (mongoose.Types.ObjectId.isValid(asinInput)) {
      or.push({ _id: new mongoose.Types.ObjectId(asinInput) });
    }

    const product = await MyProduct.findOne({ $or: or }).lean();

    const productDto = product
      ? fromMyProduct(product, extractPrice(product.currentPrice), extractPrice(product.originalPrice))
      : null;

    res.json(apiResponse(true, productDto ? 'Product found' : 'Product not found', productDto));
  } catch (e) {
    res.status(400).json(apiResponse(false, `Failed to retrieve product: ${e.message}`));
  }
}

async function fetchLivePriceBoundsInner(categoryRaw) {
  const category = String(categoryRaw || '').trim();
  const cacheKey = category
    ? `${category.toLowerCase()}:${PRICE_BOUNDS_CACHE_REVISION}`
    : `__all__:${PRICE_BOUNDS_CACHE_REVISION}`;
  const ttl = livePriceBoundsCacheTtlMs();
  if (ttl > 0) {
    const hit = livePriceBoundsCache.get(cacheKey);
    if (hit && Date.now() - hit.at < ttl) {
      return hit.value;
    }
  }

  const products = await loadProductsForCanonicalPriceBounds(category);
  let forBounds = products;
  if (category) {
    const critical = products.filter((p) => ProductRecommendationService.hasCriticalSpecs(p, category));
    if (critical.length > 0) forBounds = critical;
  }
  const canonical = getCanonicalPriceBounds(forBounds);
  const value =
    !canonical || canonical.count === 0
      ? { min: null, max: null, count: 0 }
      : { min: canonical.min, max: canonical.max, count: canonical.count };

  if (ttl > 0) {
    livePriceBoundsCache.set(cacheKey, { at: Date.now(), value });
  }
  return value;
}

async function getProductPriceBounds(req, res) {
  try {
    res.set('Cache-Control', 'no-store');

    const category = String(req.query.category || '').trim();

    if (!dbConnected()) {
      return res.json(
        apiResponse(true, 'Database not connected. No live price bounds available.', {
          category: category || 'all',
          min: null,
          max: null,
          count: 0,
        })
      );
    }

    // FAST_PRICE_BOUNDS_FROM_CATEGORY_META_V1
    // Mobile app still calls /api/products/price-bounds; answer from category metadata first.
    const escapedCategoryForBounds = String(category).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const categoryDocFastBounds = await Category.findOne({
      $or: [
        { slug: category },
        { category_slug: category },
        { key: category },
        { category: category },
        { slug: { $regex: new RegExp(`^${escapedCategoryForBounds}$`, 'i') } },
        { category_slug: { $regex: new RegExp(`^${escapedCategoryForBounds}$`, 'i') } },
        { name: { $regex: new RegExp(`^${escapedCategoryForBounds}$`, 'i') } },
        { category: { $regex: new RegExp(`^${escapedCategoryForBounds}$`, 'i') } },
      ],
    }).select('slug category_slug name category min_price max_price price_ranges').lean();

    const fastMin = Number(categoryDocFastBounds?.min_price);
    const fastMax = Number(categoryDocFastBounds?.max_price);

    if (Number.isFinite(fastMin) && fastMin > 0 && Number.isFinite(fastMax) && fastMax >= fastMin) {
      return res.json({
        success: true,
        data: {
          category,
          min: fastMin,
          max: fastMax,
          min_price: fastMin,
          max_price: fastMax,
          source: 'category_metadata_fast',
          cached: true,
        },
      });
    }

    const bounds = await fetchLivePriceBoundsInner(category);

    if (bounds.count === 0) {
      const categoryDoc = category
        ? await Category.findOne({ slug: new RegExp(`^${escapeRegex(category)}$`, 'i') }).lean()
        : null;
      // No live prices; fall back to category metadata if available
      if (categoryDoc) {
        const rangeEnds = Array.isArray(categoryDoc.price_ranges)
          ? categoryDoc.price_ranges
              .map((r) => Number(r?.end_price))
              .filter((v) => Number.isFinite(v) && v > 0)
          : [];
        const metaMax = [
          Number(categoryDoc.max_price),
          Number(categoryDoc.maxPrice),
          ...rangeEnds,
        ].filter((v) => Number.isFinite(v) && v > 0);
        const metaMin = [
          Number(categoryDoc.min_price),
          Number(categoryDoc.minPrice),
        ].filter((v) => Number.isFinite(v) && v > 0);

        return res.json(
          apiResponse(true, 'Product price bounds retrieved successfully (category metadata)', {
            category: category || 'all',
            min: metaMin.length ? Math.min(...metaMin) : null,
            max: metaMax.length ? Math.max(...metaMax) : null,
            count: 0,
          })
        );
      }

      return res.json(
        apiResponse(true, 'No active products found for this category', {
          category: category || 'all',
          min: null,
          max: null,
          count: 0,
        })
      );
    }

    return res.json(
      apiResponse(true, 'Product price bounds retrieved successfully', {
        category: category || 'all',
        min: bounds.min,
        max: bounds.max,
        count: bounds.count,
      })
    );
  } catch (e) {
    res.status(400).json(apiResponse(false, `Failed to retrieve product price bounds: ${e.message}`));
  }
}

async function getLivePriceBoundsForCategory(category) {
  const categoryFilter = buildCategoryFilter(category);
  if (!categoryFilter || !dbConnected()) {
    return { min: null, max: null, count: 0 };
  }

  // FAST_INTERNAL_BOUNDS_FROM_CATEGORY_META_V1
  // /products/top also needs catalogPriceRange; use saved category metadata first.
  const categoryKey = String(category || '').trim();
  const escapedCategoryForBounds = categoryKey.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  try {
    const categoryDocFastBounds = await Category.findOne({
      $or: [
        { slug: categoryKey },
        { category_slug: categoryKey },
        { key: categoryKey },
        { category: categoryKey },
        { slug: { $regex: new RegExp(`^${escapedCategoryForBounds}$`, 'i') } },
        { category_slug: { $regex: new RegExp(`^${escapedCategoryForBounds}$`, 'i') } },
        { name: { $regex: new RegExp(`^${escapedCategoryForBounds}$`, 'i') } },
        { category: { $regex: new RegExp(`^${escapedCategoryForBounds}$`, 'i') } },
      ],
    }).select('min_price max_price').lean();

    const fastMin = Number(categoryDocFastBounds?.min_price);
    const fastMax = Number(categoryDocFastBounds?.max_price);

    if (Number.isFinite(fastMin) && fastMin > 0 && Number.isFinite(fastMax) && fastMax >= fastMin) {
      return {
        min: fastMin,
        max: fastMax,
        count: 0,
        source: 'category_metadata_fast',
      };
    }
  } catch (error) {
    console.warn('[Products] Internal category bounds fast lookup skipped:', error.message || error);
  }

  return fetchLivePriceBoundsInner(categoryKey);
}

async function getBrandsByCategory(req, res) {
  try {
    const category = req.query.category;
    if (!category || !String(category).trim()) {
      return res.status(400).json(apiResponse(false, 'Category is required'));
    }
    if (!dbConnected()) {
      return res.status(503).json(apiResponse(false, 'Database not connected'));
    }
    const normalizedCategory = String(category).toLowerCase().trim();
    const q = typeof req.query.q === 'string' ? req.query.q.trim() : '';
    const limit = Math.min(parseInt(req.query.limit, 10) || 30, 50);
    const page = parseInt(req.query.page, 10) || 0;
    const data = await BrandService.listBrands(normalizedCategory, { q, limit, page });
    return res.json(apiResponse(true, 'Brands retrieved successfully', data));
  } catch (e) {
    const status = e.statusCode || 400;
    return res.status(status).json(apiResponse(false, e.message || 'Failed to retrieve brands'));
  }
}

async function getTopProducts(req, res) {
  try {
    const category = req.query.category;
    const budget = parseFloat(req.query.budget);
    const limit = Math.min(parseInt(req.query.limit, 10) || 5, 5);
    const brandRaw = typeof req.query.brand === 'string' ? req.query.brand.trim() : '';
    const brand = brandRaw || null;

    if (!category || !budget || budget <= 0) {
      return res.status(400).json(apiResponse(false, 'Budget must be greater than 0'));
    }
    if (brand && !isValidBrandParam(brand)) {
      return res.status(400).json(apiResponse(false, 'Invalid brand parameter'));
    }

    if (!dbConnected()) {
      return res.json(
        apiResponse(true, 'No products found within budget', {
          category,
          budget,
          count: 0,
          totalMatches: 0,
          matchType: 'none',
          priceWindow: null,
          message: 'Database not connected. Try again later.',
          selection_note: '',
          products: [],
        })
      );
    }

    const normalizedCategory = category.toLowerCase().trim();

    const brandKey = brand ? brand.toLowerCase().trim() : '';
    const topCacheKey = `cat-guard-live-budget-v1|${normalizedCategory}|${Math.floor(Number(budget))}|${limit}|${brandKey}`;
const topCacheHit = topProductsResponseCache.get(topCacheKey);
if (topCacheHit && Date.now() - topCacheHit.at < Math.min(topProductsResponseCacheTtlMs(), 30000)) {
  return res.json(topCacheHit.value);
}

if (brand) {
  const brandValid = await BrandService.isValidBrandForCategory(normalizedCategory, brand);
  if (!brandValid) {
    return res.status(400).json(
      apiResponse(false, 'Brand is not available for this category. Select a brand from the list.')
    );
  }
}

    const [recommendation, catalogPriceRange] = await Promise.all([
  LiveBudgetRecommendationService.getTopProductsForCategoryAndBudget(
    normalizedCategory,
    budget,
    { limit, ...(brand ? { brand } : {}) }
  ),
  getLivePriceBoundsForCategory(normalizedCategory).catch((error) => {
    console.warn('[Products] Price bounds lookup skipped:', error.message || error);
    return { min: null, max: null, count: 0 };
  }),
]);

const budgetCap = Math.floor(Number(budget));
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
    const similarFillCount = recommendation.similarFillCount ?? 0;
    const requestedBrand = recommendation.requestedBrand || null;
    const brandFilterApplied =
      Boolean(brand) &&
      (matchType === 'within_budget_and_brand' || matchType === 'within_budget_and_brand_partial');
    const formattedBudget = `\u20B9${budgetCap.toLocaleString('en-IN')}`;
    const categoryNouns = getCategoryProductNouns(normalizedCategory);
    let fallbackMessage = null;
    if (partialBrandFill || matchType === 'within_budget_and_brand_partial') {
      const productNoun = brandMatchCount === 1 ? categoryNouns.singular : categoryNouns.plural;
      const productVerb = brandMatchCount === 1 ? 'is' : 'are';
      const recWord = similarFillCount === 1 ? 'recommendation' : 'recommendations';
      const recVerb = similarFillCount === 1 ? 'is' : 'are';
      fallbackMessage =
        `Only ${brandMatchCount} ${requestedBrand} ${productNoun} ${productVerb} available within your budget. ` +
        `Here ${recVerb} ${similarFillCount} similar ${recWord} from other brands.`;
    } else if (fallbackApplied) {
      fallbackMessage =
        `No ${requestedBrand} ${categoryNouns.plural} found under ${formattedBudget}. Showing similar products within your budget.`;
    }

    /** Never expose a band above what the user typed (guards stale symmetric-window deployments). */
    let priceWindow = recommendation.priceWindow || null;
    if (priceWindow && priceWindow.min != null && priceWindow.max != null && budgetCap > 0) {
      const mn = Math.floor(priceWindow.min);
      const mx = Math.floor(priceWindow.max);
      priceWindow = {
        min: Math.min(Math.max(0, mn), budgetCap),
        max: Math.min(Math.max(0, mx), budgetCap),
      };
      if (priceWindow.min > priceWindow.max) {
        priceWindow = { min: priceWindow.max, max: priceWindow.max };
      }
    }

    const formattedWindowMin = priceWindow?.min != null
      ? `\u20B9${Math.floor(priceWindow.min).toLocaleString('en-IN')}`
      : formattedBudget;
    const formattedWindowMax = priceWindow?.max != null
      ? `\u20B9${Math.floor(priceWindow.max).toLocaleString('en-IN')}`
      : formattedBudget;

    let message;
    let selection_note = '';
    if (matchType === 'within_budget_and_brand') {
      message = recommendation.totalMatches > topProducts.length
        ? `Showing top ${topProducts.length} ${requestedBrand} products (budget: ${formattedBudget}).`
        : `Found ${topProducts.length} ${requestedBrand} products (budget: ${formattedBudget}).`;
    } else if (matchType === 'within_budget_and_brand_partial') {
      message = fallbackMessage || `Showing ${brandMatchCount} ${requestedBrand} and ${similarFillCount} similar products (budget: ${formattedBudget}).`;
    } else if (matchType === 'within_budget_brand_fallback') {
      message = `Showing ${topProducts.length} products within your budget (${formattedBudget}). ${fallbackMessage}`;
    } else if (matchType === 'within_budget') {
      message = recommendation.totalMatches > topProducts.length
        ? `Showing top ${topProducts.length} between ${formattedWindowMin} and ${formattedWindowMax} (entered budget: ${formattedBudget}; prices include up to this amount).`
        : `Found ${topProducts.length} between ${formattedWindowMin} and ${formattedWindowMax} (entered budget: ${formattedBudget}; prices include up to this amount).`;
      selection_note =
        'Eligible prices run from zero up to your entered budget (see priceWindow). ' +
        'Selection tries 2 Amazon + 2 Flipkart + 1 Croma (top-ranked per platform); remaining slots fill in round‑robin across Amazon → Flipkart → Croma → other when inventory allows. ' +
        'The returned list is ordered by rating (highest first), then by specifications when ratings tie. ' +
        'Ranking prefers rating, then specifications; Flipkart/Croma rely on specifications when rating is missing.';
    } else {
      if (
        catalogPriceRange?.min != null &&
        Number.isFinite(catalogPriceRange.min) &&
        budgetCap < Math.floor(catalogPriceRange.min)
      ) {
        const formattedMin = `\u20B9${Math.floor(catalogPriceRange.min).toLocaleString('en-IN')}`;
        message = `No products found under ${formattedBudget}. Try ${formattedMin} or above.`;
      } else {
        message = `No products found between ${formattedWindowMin} and ${formattedWindowMax} (entered budget: ${formattedBudget}).`;
      }
      selection_note = '';
    }

    const response = {
      category,
      budget,
      count: topProducts.length,
      totalMatches: recommendation.totalMatches || 0,
      matchType,
      requestedBrand,
      brandFilterApplied,
      fallbackApplied,
      partialBrandFill,
      brandMatchCount,
      similarFillCount,
      fallbackMessage,
      priceWindow,
      catalogPriceRange,
      livePriceRefreshCompleted: recommendation.livePriceRefreshCompleted === true,
      livePriceCandidatesChecked: recommendation.livePriceCandidatesChecked || 0,
      message,
      selection_note,
      products: topProducts,
    };

    const responseBody = apiResponse(
      true,
      topProducts.length > 0 ? 'Top products retrieved successfully' : 'No products found within budget',
      response
    );

    topProductsResponseCache.set(topCacheKey, { at: Date.now(), value: responseBody });
    return res.json(responseBody);
  } catch (e) {
    res.status(400).json(apiResponse(false, `Failed to retrieve top products: ${e.message}`));
  }
}

async function adminDeleteProduct(req, res) {
  try {
    if (!dbConnected()) {
      return res.status(503).json(apiResponse(false, 'Database not connected'));
    }

    const id = req.params.id;
    if (!mongoose.Types.ObjectId.isValid(id)) {
      return res.status(400).json(apiResponse(false, 'Invalid product id'));
    }

    const product = await MyProduct.findById(id).lean();
    if (!product) {
      return res.status(404).json(apiResponse(false, 'Product not found'));
    }

    await MyProduct.deleteOne({ _id: id });

    if (product.asin) {
      await Product.deleteMany({ asin: product.asin });
    }

    return res.json(apiResponse(true, 'Product deleted successfully', { id, asin: product.asin || null }));
  } catch (e) {
    return res.status(500).json(apiResponse(false, `Failed to delete product: ${e.message}`));
  }
}

async function adminToggleActive(req, res) {
  try {
    if (!dbConnected()) {
      return res.status(503).json(apiResponse(false, 'Database not connected'));
    }

    const id = req.params.id;
    if (!mongoose.Types.ObjectId.isValid(id)) {
      return res.status(400).json(apiResponse(false, 'Invalid product id'));
    }

    const product = await MyProduct.findById(id);
    if (!product) {
      return res.status(404).json(apiResponse(false, 'Product not found'));
    }

    const currentActive = product.isActive !== false;
    const nextActive = !currentActive;

    product.isActive = nextActive;
    product.lastUpdated = new Date();
    product.lastSeenAt = new Date();
    await product.save();

    if (product.asin) {
      await Product.updateMany(
        { asin: product.asin },
        {
          $set: {
            is_active: nextActive,
            updated_at: new Date(),
            last_seen_at: new Date(),
          },
        }
      );
    }

    return res.json(apiResponse(true, `Product ${nextActive ? 'activated' : 'deactivated'} successfully`, {
      id,
      asin: product.asin || null,
      isActive: nextActive,
    }));
  } catch (e) {
    return res.status(500).json(apiResponse(false, `Failed to toggle product status: ${e.message}`));
  }
}

module.exports = {
  getProducts,
  getProductCount,
  getProductByAsin,
  getProductPriceBounds,
  getBrandsByCategory,
  getTopProducts,
  adminDeleteProduct,
  adminToggleActive,
};

// Price caches are invalidated after live-price product writes.
module.exports.invalidatePriceCaches = function invalidatePriceCaches() {
  topProductsResponseCache.clear();
  livePriceBoundsCache.clear();
};
