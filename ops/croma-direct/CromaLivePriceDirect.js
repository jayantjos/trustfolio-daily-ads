'use strict';
// Direct Croma JSON listing price; no Scrape.do, no changes to Amazon/Flipkart worker.
const {execFile} = require('node:child_process');
const API = 'https://api.croma.com/searchservices/v1/search';
// Cap active Croma search requests; keep it adjustable if Croma starts throttling.
const MAX_CONCURRENT = Math.min(8, Math.max(1, Number.parseInt(process.env.CROMA_MAX_CONCURRENT || '8', 10) || 8));
// Existing /api/live-prices accepts up to 30 IDs; leave room for overlapping views.
const MAX_QUEUE = 64;
let active = 0;
const queue = [];
function limited(task) {
  return new Promise(resolve => {
    if (active >= MAX_CONCURRENT && queue.length >= MAX_QUEUE) {
      resolve({status:'error',in_stock:null,error:'croma queue full'});
      return;
    }
    const run = () => {
      active++;
      Promise.resolve().then(task).then(resolve, () => {
        resolve({status:'error',in_stock:null,error:'croma request failed'});
      }).finally(() => {
        active--;
        const next = queue.shift();
        if (next) next();
      });
    };
    if (active < MAX_CONCURRENT) run();
    else queue.push(run);
  });
}
function canFetchCroma(doc) {
  return String(doc && doc.platform || '').toLowerCase() === 'croma'
    && /^\d{4,12}$/.test(String(doc.platform_product_id || ''))
    && Boolean(String(doc.title || '').trim());
}
function parsePrice(v) {
  if (v && typeof v === 'object') return parsePrice(v.value ?? v.formattedValue);
  if (v == null) return null;
  const n = Number(String(v).replace(/[^0-9.]/g, ''));
  return Number.isFinite(n) && n > 0 && n < 100000000 ? n : null;
}
function buyPrice(item) {
  for (const key of ['price', 'pincodePrice']) {
    const p = item[key];
    if (String(p && p.priceType || '').toUpperCase() === 'BUY') {
      const n = parsePrice(p);
      if (n !== null) return n;
    }
  }
  for (const key of ['sellingPrice','offerPrice','finalPrice']) {
    const n = parsePrice(item[key]);
    if (n !== null) return n;
  }
  return null;
}
function curlJson(url) {
  return new Promise((resolve,reject) => {
    execFile('curl', ['-fsS','--connect-timeout','3','--max-time','5','--url',url],
      {timeout:5500, encoding:'utf8', maxBuffer:4000000}, (e,out) => {
        if (e) return reject(Error('croma HTTP request failed'));
        try {resolve(JSON.parse(out));}
        catch (_) {reject(Error('croma invalid JSON'));}
      });
  });
}
// A query page can serve many products. Deduplicate concurrent calls for 45s.
const QUERY_CACHE_MS = 45000;
const QUERY_CACHE_MAX = 200;
const queryCache = new Map();
function cachedCurlJson(url) {
  const now = Date.now();
  const cached = queryCache.get(url);
  if (cached && cached.until > now) return cached.promise;
  if (cached) queryCache.delete(url);
  const promise = curlJson(url).catch(error => { queryCache.delete(url); throw error; });
  queryCache.set(url, {promise,until:now + QUERY_CACHE_MS});
  if (queryCache.size > QUERY_CACHE_MAX) queryCache.delete(queryCache.keys().next().value);
  return promise;
}
function searchPlan(doc) {
  const title = String(doc.title).trim().replace(/\s+/g,' ').replace(/^buy\s+/i,'');
  const words = title.split(' ').filter(Boolean);
  const brand = String(doc.brand || words[0] || '').trim();
  const category = String(doc.category || '').toLowerCase();
  const kind = /washing machine|washing-machines/i.test(title + ' ' + category) ? 'washing machine'
    : /smartwatch|\bwatch\b|smart-watches/i.test(title + ' ' + category) ? 'smartwatch'
    : /headphone|earbud/i.test(title + ' ' + category) ? 'headphones'
    : /laptop/i.test(title + ' ' + category) ? 'laptop'
    : /\b5g\b|mobile|smart-phone/i.test(title + ' ' + category) ? 'smartphone'
    : /\btv\b|television|smart-tvs/i.test(title + ' ' + category) ? 'tv' : '';
  // Croma search uses zero-based pages. Try precise model first, broad matches later.
  // Restrict broad searches to 3 pages and use a shared short-lived query cache.
  const candidates = [
    { query: words.slice(0,3).join(' '), pages: 1 },
    { query: words.slice(0,2).join(' '), pages: 1 },
    { query: kind ? (brand + ' ' + kind).trim() : '', pages: 3 },
    { query: brand, pages: 3 }
  ];
  const seen = new Set();
  return candidates.filter(p => {
    const key = p.query.toLowerCase();
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
async function directFetch(doc) {
  if (!canFetchCroma(doc)) return {status:'error',error:'missing croma SKU/title'};
  const sku = String(doc.platform_product_id);
  let receivedSearchData = false;
  for (const plan of searchPlan(doc)) {
    for (let page = 0; page < plan.pages; page++) {
      const params = new URLSearchParams({
        currentPage:String(page), query:plan.query + ' :relevance',
        fields:'FULL', channel:'WEB', channelCode:'400049', spellOpt:'DEFAULT'
      });
      let response;
      try { response = await cachedCurlJson(API + '?' + params.toString()); }
      catch (_) { break; }
      if (!response || !Array.isArray(response.products)) break;
      receivedSearchData = true;
      const rows = response.products;
      const hit = rows.find(row => row && ['code','skuId','productCode','id'].some(
        key => row[key] != null && String(row[key]) === sku));
      if (hit) {
        const n = buyPrice(hit);
        if (n == null) return {status:'no_price',in_stock:null};
        // BUY price verified; local delivery/stock still unknown.
        return {status:'ok',priceNum:n,in_stock:null,availability:null};
      }
      const totalPages = Number(response.pagination && response.pagination.totalPages);
      if (!rows.length || (Number.isFinite(totalPages) && totalPages > 0 && page + 1 >= totalPages)) break;
    }
  }
  // Missing from search is not proof of out-of-stock; never archive this listing.
  return receivedSearchData ? {status:'no_price',in_stock:null} :
    {status:'error',in_stock:null,error:'croma search unavailable'};
}
async function fetchCromaDirect(doc) { return limited(() => directFetch(doc)); }
module.exports={canFetchCroma,fetchCromaDirect};