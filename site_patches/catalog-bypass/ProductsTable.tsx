'use client';

import { useEffect, useState } from 'react';
import Image from 'next/image';
import { LivePrice, Product } from '@/types/product';
import { productService } from '@/services/api.service';

type CatalogProduct = Product & { skip_live_price_check?: boolean };

interface ProductsTableProps {
    products: CatalogProduct[];
    /** Budget cap in INR; listings whose live price is above it are hidden */
    maxPrice?: number;
}

type KeySpecEntry = [string, string | number];
type SupportedPlatform = 'amazon' | 'flipkart' | 'myntra' | 'paytm' | 'croma' | 'other';

function BrandRecommendationTag({ product }: { product: Product }) {
    if (product.isRequestedBrandMatch === false) {
        return (
            <span className="text-[10px] font-medium text-amber-200 bg-amber-500/20 border border-amber-400/25 px-1.5 py-0.5 rounded">
                Similar
            </span>
        );
    }
    if (product.isRequestedBrandMatch === true) {
        return (
            <span className="text-[10px] font-medium text-purple-200 bg-purple-500/20 border border-purple-400/25 px-1.5 py-0.5 rounded">
                Your brand
            </span>
        );
    }
    return null;
}

function formatReviewCount(totalReviews?: string | null): string | null {
    const raw = String(totalReviews ?? '').trim();
    if (!raw) return null;

    const digits = raw.replace(/[^\d]/g, '');
    const count = Number.parseInt(digits, 10);
    if (!Number.isFinite(count) || count <= 0) return null;

    if (count >= 1000) {
        return `${(count / 1000).toFixed(count >= 10000 ? 0 : 1)}k`;
    }
    return count.toLocaleString('en-IN');
}

function ProductRating({
    rating,
    reviews,
    compact = false,
}: {
    rating?: string | null;
    reviews?: string | null;
    compact?: boolean;
}) {
    const reviewLabel = formatReviewCount(reviews);
    const ratingValue = String(rating ?? '').trim();
    if (!ratingValue && !reviewLabel) return null;

    return (
        <span
            className={`inline-flex items-center gap-0.5 ${
                compact ? 'text-[11px] text-gray-400' : 'text-xs text-gray-300'
            }`}
        >
            {ratingValue && (
                <>
                    <span className="text-yellow-400">★</span>
                    <span className="text-white/90">{ratingValue}</span>
                </>
            )}
            {reviewLabel && <span>({reviewLabel})</span>}
        </span>
    );
}


function trackAmazonClick(platform: SupportedPlatform, buyUrl: string, title?: string) {
    try {
        if (platform !== 'amazon') return;
        if (!buyUrl || buyUrl === '#') return;

        const payload = JSON.stringify({
            platform: 'amazon',
            url: buyUrl,
            title: title || '',
            page:
                typeof window !== 'undefined'
                    ? window.location.pathname + window.location.search
                    : '',
        });

        if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
            const blob = new Blob([payload], { type: 'application/json' });
            navigator.sendBeacon('/api/track-click/', blob);
            return;
        }

        fetch('/api/track-click/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: payload,
            keepalive: true,
        }).catch(() => {});
    } catch {}
}

const FALLBACK_PRODUCT_IMAGE = '/logo.png';
const EMPTY_IMAGE_VALUES = new Set([
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

function getSafeImageSrc(src?: string | null): string {
    const normalized = String(src ?? '').trim();
    if (!normalized || EMPTY_IMAGE_VALUES.has(normalized.toLowerCase())) {
        return FALLBACK_PRODUCT_IMAGE;
    }
    return normalized;
}

function ProductImage({ src, alt, className }: { src?: string | null; alt: string; className?: string }) {
    const safeSrc = getSafeImageSrc(src);
    const [imageSrc, setImageSrc] = useState(safeSrc);

    useEffect(() => {
        setImageSrc(getSafeImageSrc(src));
    }, [src]);

    return (
        <Image
            src={imageSrc}
            alt={alt || 'Product image'}
            fill
            sizes="(min-width: 1024px) 80px, 30vw"
            className={className}
            onError={() => {
                if (imageSrc !== FALLBACK_PRODUCT_IMAGE) {
                    setImageSrc(FALLBACK_PRODUCT_IMAGE);
                }
            }}
        />
    );
}

function formatRawPlatformLabel(raw?: string | null): string {
  const t = String(raw ?? '').trim();
  if (!t) return 'Store';
  return t.charAt(0).toUpperCase() + t.slice(1).toLowerCase();
}

const KNOWN_BRAND_LABELS: Record<string, string> = {
    realme: 'Realme',
    oneplus: 'OnePlus',
    iqoo: 'iQOO',
    poco: 'POCO',
    oppo: 'OPPO',
    vivo: 'vivo',
    xiaomi: 'Xiaomi',
    redmi: 'Redmi',
    samsung: 'Samsung',
    apple: 'Apple',
    motorola: 'Motorola',
    nokia: 'Nokia',
    google: 'Google',
    nothing: 'Nothing',
    honor: 'Honor',
    huawei: 'Huawei',
    asus: 'ASUS',
    sony: 'Sony',
    lg: 'LG',
    hp: 'HP',
    dell: 'Dell',
    lenovo: 'Lenovo',
    infinix: 'Infinix',
    tecno: 'Tecno',
    lava: 'Lava',
    micrmax: 'Micromax',
    micromax: 'Micromax',
};

function formatBrandName(brand?: string | null): string {
    const raw = String(brand ?? '').trim();
    if (!raw) return '';
    const key = raw.toLowerCase();
    if (KNOWN_BRAND_LABELS[key]) return KNOWN_BRAND_LABELS[key];
    return raw
        .split(/\s+/)
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(' ');
}

function ProductBrandLabel({ brand, compact = false }: { brand?: string | null; compact?: boolean }) {
    const label = formatBrandName(brand);
    if (!label) return null;

    return (
        <span
            className={
                compact
                    ? 'inline-flex items-center text-[11px] font-semibold text-blue-100 bg-blue-500/25 border border-blue-400/35 px-1.5 py-0.5 rounded'
                    : 'inline-flex items-center text-xs font-semibold text-blue-100 bg-blue-500/25 border border-blue-400/35 px-2 py-1 rounded'
            }
        >
            {label}
        </span>
    );
}

function isHiddenSpecKey(key: string): boolean {
  return /^highlights?$/i.test(String(key).trim());
}

function normalizeSpecValue(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  const text = String(value).trim();
    return text ? text : null;
}

function addSpec(specs: KeySpecEntry[], key: string, value: unknown) {
  if (String(key || '').trim().toLowerCase() === 'network') return;
  const normalized = normalizeSpecValue(value);
  if (!normalized) return;
  if (specs.some(([existingKey]) => existingKey.toLowerCase() === key.toLowerCase())) return;
  specs.push([key, normalized]);
}

function mapToEntries(map?: Record<string, unknown> | null): KeySpecEntry[] {
  if (!map || typeof map !== 'object') return [];
  return Object.entries(map)
    .filter(([, value]) => normalizeSpecValue(value) !== null)
    .map(([key, value]) => [key, String(value)] as KeySpecEntry);
}

function extractTitleSpecs(title: string): KeySpecEntry[] {
  // TrustFolio final rule:
  // Do not derive specs from title on frontend.
  // Frontend must show only API/DB specifications.
  void title;
  return [];
}

function getDisplaySpecs(product: Product): KeySpecEntry[] {
    // TrustFolio final rule:
    // Show only cleaned DB/API specifications.
    // No title fallback. No generated specs. No extra duplicate fields.
    const selected: KeySpecEntry[] = [];

    const rawSpecs = product.specifications || {};
    if (rawSpecs && typeof rawSpecs === 'object') {
        Object.entries(rawSpecs).forEach(([key, value]) => {
            addSpec(selected, key, value);
        });
    }

    return selected.slice(0, 4);
}

export default function ProductsTable({ products, maxPrice }: ProductsTableProps) {
    const [sortBy] = useState<'recommended' | 'price' | 'rating' | 'name'>('recommended');
    const [sortOrder] = useState<'asc' | 'desc'>('desc');
    // Preserve backend ranking when "recommended" is selected
    const sortedProducts = sortBy === 'recommended' ? products : [...products].sort((a, b) => {
        let aValue: string | number;
        let bValue: string | number;

        switch (sortBy) {
            case 'price':
                aValue = a.price_inr;
                bValue = b.price_inr;
                break;
            case 'rating':
                aValue = parseFloat(a.average_rating);
                bValue = parseFloat(b.average_rating);
                break;
            case 'name':
                aValue = a.title.toLowerCase();
                bValue = b.title.toLowerCase();
                break;
            default:
                aValue = a.price_inr;
                bValue = b.price_inr;
        }

        if (sortOrder === 'asc') {
            return (aValue as number) - (bValue as number);
        } else {
            return (bValue as number) - (aValue as number);
        }
    });

    // Live Amazon, Flipkart and Croma prices: stored price renders first, verified live replaces it.
    const [livePrices, setLivePrices] = useState<Record<string, LivePrice>>({});
    const [livePending, setLivePending] = useState(false);
    const productIdsKey = products.filter((p) => !p.skip_live_price_check).map((p) => p.id).filter(Boolean).join(',');

    useEffect(() => {
        const ids = productIdsKey ? productIdsKey.split(',') : [];
        if (!ids.length) return;
        const controller = new AbortController();
        setLivePending(true);
        productService
            .getLivePrices(ids, controller.signal)
            .then((res) => {
                if (!res.success || !Array.isArray(res.data)) return;
                setLivePrices(Object.fromEntries(res.data.map((row) => [row.id, row])));
            })
            .catch(() => {}) // keep showing stored prices
            .finally(() => {
                if (!controller.signal.aborted) setLivePending(false);
            });
        return () => controller.abort();
    }, [productIdsKey]);

    // Stored prices can be stale: a listing that matched the budget may now cost more live.
    const isOverBudget = (product: CatalogProduct) => {
        if (product.skip_live_price_check) return false;
        const live = livePrices[product.id]?.live;
        return Boolean(maxPrice && live?.status === 'ok' && live.price_inr && live.price_inr > maxPrice);
    };

    // Listings found out of stock are deleted server-side; drop them from the table, along with
    // listings now over budget.
    const visibleProducts = sortedProducts.filter((p) => p.skip_live_price_check || (!livePrices[p.id]?.deleted && !isOverBudget(p)));

    const getPriceView = (product: CatalogProduct) => {
        if (product.skip_live_price_check) return { price: product.price_inr, state: 'stored' } as const;
        const row = livePrices[product.id];
        const live = row?.live;
        const platform = normalizePlatform(product.platform);
        const canBeLive = platform === 'amazon' || platform === 'flipkart' || platform === 'croma';
        if (live && live.price_inr && (live.status === 'ok' || live.status === 'out_of_stock')) {
            return { price: live.price_inr, state: live.status === 'ok' ? 'live' : 'out_of_stock' } as const;
        }
        if (livePending && canBeLive && !row) {
            return { price: product.price_inr, state: 'checking' } as const;
        }
        return { price: product.price_inr, state: 'stored' } as const;
    };

    const renderPriceTag = (state: ReturnType<typeof getPriceView>['state'], compact = false) => {
        const size = compact ? 'text-[9px] px-1 py-0' : 'text-[10px] px-1.5 py-0.5';
        if (state === 'live') {
            return (
                <span className={`inline-flex items-center gap-1 rounded bg-green-500/20 text-green-300 font-semibold ${size}`}>
                    <span className="h-1.5 w-1.5 rounded-full bg-green-400 animate-pulse" />
                    Live
                </span>
            );
        }
        if (state === 'out_of_stock') {
            return <span className={`rounded bg-red-500/20 text-red-300 font-semibold ${size}`}>Out of stock</span>;
        }
        if (state === 'checking') {
            return <span className={`text-blue-200/70 ${compact ? 'text-[9px]' : 'text-[10px]'}`}>Checking live…</span>;
        }
        return null;
    };

    const normalizePlatform = (platform?: string | null): SupportedPlatform => {
        const value = String(platform ?? '').trim().toLowerCase();
        if (!value) return 'other';
        if (value.includes('flipkart')) return 'flipkart';
        if (value.includes('croma')) return 'croma';
        if (value.includes('myntra')) return 'myntra';
        if (value.includes('paytm')) return 'paytm';
        if (value.includes('amazon')) return 'amazon';
        return 'other';
    };

    const getPlatformIcon = (platform: SupportedPlatform) => {
        const icons: Record<SupportedPlatform, string> = {
            amazon: '🛒',
            flipkart: '🛍️',
            myntra: '👗',
            paytm: '💳',
            croma: '🏬',
            other: '🏪',
        };
        return icons[platform];
    };

    const getPlatformLabel = (platform: SupportedPlatform, rawPlatform?: string | null) => {
        if (platform === 'other') return formatRawPlatformLabel(rawPlatform);
        const labels: Record<Exclude<SupportedPlatform, 'other'>, string> = {
            amazon: 'Amazon',
            flipkart: 'Flipkart',
            myntra: 'Myntra',
            paytm: 'Paytm',
            croma: 'Croma',
        };
        return labels[platform];
    };

    // Build affiliate URL for Amazon using ASIN and partner tag
    const buildAmazonAffiliateUrl = (product: Product): string => {
        const affiliateTag = 'trustfolio62804-21';
        // Prefer ASIN if present
        if (product.asin) {
            return `https://www.amazon.in/dp/${product.asin}?tag=${affiliateTag}`;
        }
        if (product.product_url) return product.product_url;
        return `https://www.amazon.in/?tag=${affiliateTag}`;
    };

    const buildProductUrl = (product: Product) => {
        const platform = normalizePlatform(product.platform);
        if (platform === 'amazon') return buildAmazonAffiliateUrl(product);
        return product.product_url || '#';
    };

    const getBuyButtonText = (platform: SupportedPlatform, rawPlatform?: string | null, compact = false) => {
        if (compact) return 'Buy Now';
        if (platform === 'amazon') return 'Buy Now On Amazon';
        if (platform === 'flipkart') return 'Buy Now On Flipkart';
        if (platform === 'croma') return 'Buy Now On Croma';
        return `Buy Now On ${getPlatformLabel(platform, rawPlatform)}`;
    };

    const buyButtonClass =
        'inline-flex h-10 items-center justify-center rounded-lg px-4 text-sm font-semibold text-white transition-colors shrink-0';

    const mobileBuyButtonClass =
        'inline-flex h-8 items-center justify-center gap-1 rounded-lg px-3 text-[11px] font-semibold text-white transition-colors shrink-0';

    return (
        <div className="bg-white/10 backdrop-blur-md rounded-2xl border border-white/20 overflow-hidden">
            {/* Table Header with Controls */}
            <div className="p-6 border-b border-white/20 bg-white/5">
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                    <div>
                        <h3 className="text-xl font-bold text-white mb-1">Recommended Products</h3>
                        <p className="text-blue-200 text-sm">Top picks matched to your budget</p>
                    </div>
                </div>
            </div>

            {/* Desktop Table View */}
            <div className="hidden lg:block overflow-x-auto">
                <table className="w-full">
                    <thead>
                    <tr className="bg-white/5 border-b border-white/20">
                        <th className="text-left p-4 text-white font-semibold min-w-80">Product</th>
                        <th className="text-left p-4 text-white font-semibold w-32">Price</th>
                        <th className="text-left p-4 text-white font-semibold w-32">Rating</th>
                        <th className="text-left p-4 text-white font-semibold w-40">Key Specs</th>
                        <th className="text-left p-4 text-white font-semibold w-48">Platforms</th>
                        <th className="text-left p-4 text-white font-semibold w-32">Action</th>
                    </tr>
                    </thead>
                    <tbody>
                    {visibleProducts.map((product, index) => {
                        const platform = normalizePlatform(product.platform);
                        const buyUrl = buildProductUrl(product);
                        const keySpecs = getDisplaySpecs(product);
                        const specsToShow = keySpecs.slice(0, 5);
                        const isBestProduct = index === 0;
                        const priceView = getPriceView(product);
                        const truncate = (text: string, max = 80) =>
                            text.length > max ? `${text.slice(0, max - 1)}…` : text;

                        return (
                        <tr
                            key={product.id}
                            className="border-b border-white/10 hover:bg-white/5 transition-colors"
                        >
                            <td className="p-4">
                                <div className="flex items-start gap-4">
                                    <div className="relative w-20 h-20 rounded-lg overflow-hidden flex-shrink-0">
                                        <ProductImage
                                            src={product.main_image}
                                            alt={product.title}
                                            className="object-cover"
                                        />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        {isBestProduct && (
                                            <div className="mb-2 text-xs font-semibold text-yellow-300">
                                                Best Choice
                                            </div>
                                        )}
                                        <h4 className="font-semibold text-white text-sm mb-1 line-clamp-2">
                                            {product.title}
                                        </h4>
                                        <div className="flex items-center gap-2 mb-2 flex-wrap">
                        <ProductBrandLabel brand={product.brand} />
                                            <BrandRecommendationTag product={product} />
                                            {product.in_stock && priceView.state !== 'out_of_stock' && (
                                                <span className="text-xs text-green-300 bg-green-500/20 px-2 py-1 rounded">
                            In Stock
                          </span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </td>

                            <td className="p-4">
                                <div className="text-right">
                                    <div className="text-lg font-bold text-white">
                                        ₹{priceView.price.toLocaleString('en-IN')}
                                    </div>
                                    <div className="flex justify-end">{renderPriceTag(priceView.state)}</div>
                                    {product.original_price_inr && product.original_price_inr > priceView.price && (
                                        <div className="text-xs text-gray-400 line-through">
                                            ₹{product.original_price_inr.toLocaleString('en-IN')}
                                        </div>
                                    )}
                                </div>
                            </td>

                            <td className="p-4">
                                <div className="flex items-center gap-1">
                                    <span className="text-yellow-400">★</span>
                                    <span className="text-white font-medium">{product.average_rating}</span>
                                </div>
                                <div className="text-xs text-blue-200">
                                    ({product.total_reviews})
                                </div>
                            </td>

                            <td className="p-4">
                                {specsToShow.length > 0 ? (
                                    <ul className="space-y-1 text-xs leading-snug text-white">
                                        {specsToShow.map(([key, value], idx) => (
                                            <li key={`${key}-${idx}`} className="flex gap-1">
                                                <span className="text-blue-300 whitespace-nowrap">{key}:</span>
                                                <span className="text-white/90">{truncate(String(value), 90)}</span>
                                            </li>
                                        ))}
                                    </ul>
                                ) : (
                                    <div className="text-xs text-gray-400">N/A</div>
                                )}
                            </td>

                            <td className="p-4">
                                <div className="flex flex-wrap gap-1">
                                    <div className="flex items-center gap-1 text-xs bg-white/10 rounded px-2 py-1">
                                        <span>{getPlatformIcon(platform)}</span>
                                        <span className="text-white">{getPlatformLabel(platform, product.platform)}</span>
                                    </div>
                                </div>
                            </td>

                            <td className="p-2">
                                <a
                                    href={buyUrl}
                                        onClick={() => trackAmazonClick(platform, buyUrl, product.title)}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className={`${buyButtonClass} ${
                                        buyUrl === '#'
                                            ? 'bg-gray-600 cursor-not-allowed pointer-events-none'
                                            : 'bg-gradient-to-r from-green-600 to-green-700 hover:from-green-700 hover:to-green-800'
                                    }`}
                                >
                                    {buyUrl === '#' ? 'URL Not Available' : getBuyButtonText(platform, product.platform)}
                                </a>
                            </td>
                        </tr>
                    );
                    })}
                    </tbody>
                </table>
            </div>

            {/* Mobile Table View */}
            <div className="lg:hidden">
                {/* Mobile Table Header */}
                <div className="bg-white/5 border-b border-white/20 px-3 py-2.5">
                    <div className="flex items-center justify-end">
                        <span className="text-blue-200 text-sm">
                            {sortedProducts.length} products
                        </span>
                    </div>
                </div>

                {/* Mobile Table Rows */}
                <div className="p-3 space-y-3">
                    {visibleProducts.map((product, index) => {
                        const platform = normalizePlatform(product.platform);
                        const buyUrl = buildProductUrl(product);
                        const isBestProduct = index === 0;
                        const specs = getDisplaySpecs(product).slice(0, 4);
                        const priceView = getPriceView(product);
                        const hasDiscount =
                            product.original_price_inr &&
                            product.original_price_inr > priceView.price;

                        return (
                        <div
                            key={product.id}
                            className="flex items-center gap-2 p-2 rounded-xl border border-white/10 bg-white/[0.02] transition-colors duration-200 hover:bg-white/[0.05]"
                        >
                            {/* Image — responsive aspect ratio, vertically centered */}
                            <div className="relative w-[5.25rem] sm:w-[6rem] shrink-0 aspect-[3/4] overflow-hidden rounded-lg bg-white/5">
                                <ProductImage
                                    src={product.main_image}
                                    alt={product.title}
                                    className="object-contain object-center"
                                />
                                {isBestProduct && (
                                    <span className="absolute inset-x-0 top-0 bg-yellow-500/95 text-[9px] font-bold uppercase tracking-wide text-center py-0.5 text-black z-10">
                                        Best
                                    </span>
                                )}
                            </div>

                            {/* Content — remaining width */}
                            <div className="flex-1 min-w-0 py-0 pr-0.5 flex flex-col gap-1.5">
                                <h4 className="font-semibold text-white text-[12px] leading-snug line-clamp-2">
                                    {product.title}
                                </h4>

                                <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1">
                                    <ProductBrandLabel brand={product.brand} compact />
                                    <BrandRecommendationTag product={product} />
                                    <ProductRating
                                        rating={product.average_rating}
                                        reviews={product.total_reviews}
                                        compact
                                    />
                                </div>

                                <div className="flex items-center justify-between gap-2">
                                    {specs.length > 0 ? (
                                        <div className="flex flex-wrap gap-1 min-w-0 flex-1">
                                            {specs.map(([key, value], specIdx) => (
                                                <span
                                                    key={`${key}-${specIdx}`}
                                                    className="inline-flex max-w-full items-center gap-1 rounded-md bg-white/[0.06] border border-white/10 px-1 py-0.5 text-[9px] leading-tight text-white/85"
                                                >
                                                    <span className="text-blue-300/90 shrink-0">{key}</span>
                                                    <span className="truncate">{value}</span>
                                                </span>
                                            ))}
                                        </div>
                                    ) : (
                                        <div className="flex-1" />
                                    )}
                                    <div className="flex flex-col items-end shrink-0 leading-none">
                                        <span className="text-[17px] font-bold text-white whitespace-nowrap">
                                            ₹{priceView.price.toLocaleString('en-IN')}
                                        </span>
                                        <span className="mt-0.5">{renderPriceTag(priceView.state, true)}</span>
                                        {hasDiscount && (
                                            <span className="text-[9px] text-gray-500 line-through whitespace-nowrap mt-0.5">
                                                ₹{product.original_price_inr!.toLocaleString('en-IN')}
                                            </span>
                                        )}
                                    </div>
                                </div>

                                <div className="flex items-center gap-1.5 rounded-lg bg-white/[0.04] border border-white/10 px-2 py-1 mt-auto">
                                    <div className="flex min-w-0 flex-1 items-center gap-1 text-[10px] text-gray-300">
                                        <span className="shrink-0">{getPlatformIcon(platform)}</span>
                                        <span className="truncate">{getPlatformLabel(platform, product.platform)}</span>
                                    </div>
                                    <a
                                        href={buyUrl}
                                        onClick={() => trackAmazonClick(platform, buyUrl, product.title)}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className={`${mobileBuyButtonClass} ${
                                            buyUrl === '#'
                                                ? 'bg-gray-600/80 cursor-not-allowed pointer-events-none'
                                                : 'bg-green-600 hover:bg-green-500 active:bg-green-700'
                                        }`}
                                    >
                                        {buyUrl === '#' ? 'Unavailable' : getBuyButtonText(platform, product.platform, true)}
                                        {buyUrl !== '#' && (
                                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
                                            </svg>
                                        )}
                                    </a>
                                </div>

                                {product.feature_bullets && product.feature_bullets.length > 0 && (
                                    <div className="flex flex-wrap gap-1">
                                        {product.feature_bullets.slice(0, 2).map((feature, idx) => {
                                            const parts = feature.split('【');
                                            if (parts.length > 1) {
                                                return (
                                                    <span
                                                        key={idx}
                                                        className="text-[10px] bg-white/5 text-gray-400 px-1.5 py-0.5 rounded border border-white/5"
                                                    >
                                                        {parts[1].split('】')[0]}
                                                    </span>
                                                );
                                            }
                                            return null;
                                        })}
                                    </div>
                                )}
                            </div>
                        </div>
                        );
                    })}
                </div>

                {/* Mobile Table Footer */}
                <div className="bg-white/5 border-t border-white/20 px-3 py-2.5">
                    <div className="flex items-center justify-end text-sm">
                        <span className="text-blue-200">
                            {sortedProducts.length} products shown
                        </span>
                    </div>
                </div>
            </div>

            {/* No Products Message */}
            {products.length === 0 && (
                <div className="text-center py-12">
                    <div className="w-16 h-16 bg-gradient-to-br from-gray-500 to-gray-600 rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2M4 13h2m8-6v6.01M12 17h.01" />
                        </svg>
                    </div>
                    <h3 className="text-lg font-semibold text-white mb-2">No Products to Display</h3>
                    <p className="text-blue-200">Try adjusting your filters to see products</p>
                </div>
            )}
        </div>
    );
}
