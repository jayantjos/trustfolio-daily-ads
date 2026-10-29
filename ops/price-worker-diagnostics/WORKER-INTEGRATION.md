# TrustFolio Amazon & Flipkart Cloudflare Worker price repair

## Deployment status
Worker-ready source and tests are ready. They are NOT installed in the existing developer-owned Cloudflare Worker. We have no direct edit access to that account or its source repo.

## Evidence from 29 October 2026
- Exact Flipkart POCO X8 Pro Max (Blue, 512 GB) PID MOBHH2KYWG8UBBAF had old MongoDB stored price INR 52999. User screenshot on Flipkart showed INR 49999.
- Existing Worker received HTTP 200 and 366.5 KB, but reported not_listed and no price for the exact URL, cached and uncached.
- VPS curl received HTTP 200 and 375 KB, with exact PID and title, but NO offers, ppd/fsp, JSON-LD, INR 49999 or INR 52999 in returned HTML.
- Two other Flipkart products worked with existing Worker: OPPO Reno 12 Pro and Tecno Pova 8 Pro. The issue is product/response specific.
- Do NOT hardcode INR 49999: price can vary by seller, pincode, time and account.

## Scrape.do historical source references
- https://github.com/jayantjos/trustfolio-scraper/blob/main/app/price_maintenance.py
- https://github.com/jayantjos/trustfolio-scraper/blob/main/legacy_price/scripts/price_update_worker.py
- https://github.com/jayantjos/trustfolio-scraper/blob/main/extractors/listing_evidence.py

Flipkart old extraction priority:
1. Current PRODUCT schema.org Product/Offer price, and in-stock availability.
2. PDP embedded ppd.fsp, which is the selling price (not ppd.mrp and not automatically ppd.finalPrice).
3. Product metadata price. Be careful: the visible Buy at value can be a conditional card/bank-offer price and should not be treated as base sale price without evidence.
4. Do not confuse sponsored/recommended products, EMI, exchange, MRP or strike price with the current product.

Amazon old price reference: Scrape.do Amazon PDP plugin returned top-level price for the exact ASIN. The old script explicitly avoided list_price as live price. In the new Worker use exact ASIN, primary Amazon buy-box or structured Offer price, not crossed-out MRP or recommendations. Ensure correct India currency, pincode and seller selection.

## Developer Worker integration
Copy WorkerPriceExtractionRules.mjs alongside the existing Worker source and import it. The file is pure JavaScript compatible with Cloudflare Worker module mode. This is the integration shape; adapt variable names to existing Worker:

    import { extractLiveStorePrice } from "./WorkerPriceExtractionRules.mjs";

    const parsed = extractLiveStorePrice({
      platform: "flipkart",
      html: receivedHtml,
      id: expectedPid,
      title: expectedTitle,
    });

    // On parsed.status==="ok", place parsed.priceNum, parsed.price,
    // parsed.inStock, and parsed.source into the existing
    // response.results[0].flipkart object.
    // Preserve original /api/check request/response contract.

If Worker fetched HTTP 200 and received a real product page, but the price is not exposed, return status="error", error="product_page_price_not_exposed", priceNum=null. Do NOT return not_listed or not_available, and do NOT mark the item out of stock.

If source HTML has no price (confirmed for POCO), JS parsing alone cannot manufacture it. Developer should find the exact PDP's JavaScript-rendered or structured offer response for the SAME PID/variant and user pincode through permitted interfaces, and test. Cloudflare Browser Run /content supports rendered HTML as a conditional diagnostic; use only on bounded missing-price cases, subject to cost/availability and marketplace access rules. A rendered browser may still fail or get an error. Do not enable unlimited rendered fetches.

Cloudflare docs:
https://developers.cloudflare.com/browser-run/quick-actions/content-endpoint/
https://developers.cloudflare.com/browser-run/pricing/

## Identity requirements
Always validate exact Flipkart PID and product variant (color, capacity, RAM) or Amazon ASIN. If the page appears to be a different product or variant, return an error, never an unrelated price.

## Regression checklist
- POCO Blue 512 GB PID MOBHH2KYWG8UBBAF: if priced source absent, must return error rather than not_listed or made-up price.
- Previously successful Flipkart SKUs MOBH2AHZH779MGYF and MOBHQFDZKKM7EEFZ must still return positive verified prices.
- One Amazon ASIN with a known selling price and distinct MRP must return selling price only.
- 502, 429, 403, timeout, CAPTCHA, empty response or parser failure must not delete product.
- Croma bypasses this Worker; preserve existing VPS direct Croma path.
- Keep existing /api/check request body containing items array and useCache and result objects named flipkart/amazon.

## Tests
Run: node --test ops/price-worker-diagnostics/WorkerPriceExtractionRules.test.mjs

The tests are synthetic fixtures and pass. Live read-only test on real POCO raw HTML found no price. This package cannot by itself update the POCO price before the Worker gains a genuine price-bearing response.

## Access needed
The active Worker hostname is spring-shape-2759.1shailendrasoni1.workers.dev and is managed in another person's Cloudflare account. Have that account owner import and test this patch or provide its source repository. Never paste any secret API keys, service tokens or credentials.
