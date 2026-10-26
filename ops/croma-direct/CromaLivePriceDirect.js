'use strict';
// Direct Croma JSON listing price; no Scrape.do, no changes to Amazon/Flipkart worker.
const {execFile} = require('node:child_process');
const API = 'https://api.croma.com/searchservices/v1/search';
const MAX_CONCURRENT = 3;
const MAX_QUEUE = 12;
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
function searchQueries(doc) {
  const title = String(doc.title).trim().replace(/\s+/g,' ');
  const brand = String(doc.brand || title.split(' ')[0]).trim();
  const kind = /washing machine/i.test(title) ? 'washing machine'
    : /smartwatch|\bwatch\b/i.test(title) ? 'smartwatch'
    : /laptop/i.test(title) ? 'laptop'
    : /\b5g\b|mobile/i.test(title) ? 'smartphone'
    : String(doc.category || '').trim();
  return [...new Set([title.split(' ').slice(0,6).join(' '),
    (brand + ' ' + kind).trim()].filter(Boolean))].slice(0,2);
}
async function directFetch(doc) {
  if (!canFetchCroma(doc)) return {status:'error',error:'missing croma SKU/title'};
  const sku = String(doc.platform_product_id);
  for (const query of searchQueries(doc)) {
    const params = new URLSearchParams({
      currentPage:'1', query:query + ' :relevance', fields:'FULL',
      channel:'WEB', channelCode:'400049', spellOpt:'DEFAULT'
    });
    let response;
    try { response = await curlJson(API + '?' + params.toString()); }
    catch (_) { continue; }
    const rows = Array.isArray(response && response.products) ? response.products : [];
    const hit = rows.find(row => row && ['code','skuId','productCode','id'].some(
      key => row[key] != null && String(row[key]) === sku));
    if (!hit) continue;
    const n = buyPrice(hit);
    if (n == null) return {status:'no_price',in_stock:null};
    // Search-listing price is proven; delivery-PIN stock is NOT.
    return {status:'ok',priceNum:n,in_stock:null,availability:null};
  }
  // Empty/unmatched search result must never be interpreted as OOS.
  return {status:'no_price'};
}
async function fetchCromaDirect(doc) { return limited(() => directFetch(doc)); }
module.exports={canFetchCroma,fetchCromaDirect};