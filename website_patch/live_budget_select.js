'use strict';

/** Final Top-5 selection after the same live-price refresh as the website. */
function selectLiveBudgetTop(candidates, rows, budget, limit = 5) {
  const cap = Math.floor(Number(budget));
  if (!Number.isFinite(cap) || cap < 1) throw new Error('Invalid budget');
  if (!Array.isArray(candidates) || !Array.isArray(rows)) throw new Error('Missing product rows');
  const max = Math.min(5, Math.max(1, Math.floor(limit)));
  const byId = new Map();
  for (const r of rows) {
    if (!r || !r.id || byId.has(String(r.id))) throw new Error('Invalid live-price response');
    byId.set(String(r.id), r);
  }
  const seen = new Set(), eligible = [];
  for (const product of candidates) {
    if (!product || !product.id) continue;
    const id = String(product.id);
    if (seen.has(id)) continue;
    seen.add(id);
    const row = byId.get(id);
    if (!row || row.deleted || row.live?.status === 'out_of_stock') continue;
    const hasLive = row.live?.status === 'ok';
    const price = Number(hasLive ? row.live.price_inr : product.price_inr);
    if (!Number.isFinite(price) || price <= 0 || price > cap) continue;
    eligible.push({
      ...product,
      price_inr: price,
      price_source: hasLive ? 'website_live_price' : 'catalog_fallback',
      live_price_status: row.live?.status || null,
    });
  }
  const platform = (product) => {
    const p = String(product.platform || '').toLowerCase();
    if (p.includes('amazon')) return 'amazon';
    if (p.includes('flipkart')) return 'flipkart';
    if (p.includes('croma')) return 'croma';
    return 'other';
  };
  const pools = Object.fromEntries(['amazon','flipkart','croma','other'].map(k=>[k,[]]));
  eligible.forEach((p,i)=>pools[platform(p)].push({p,i}));
  const picked = [], used = new Set();
  const take = (kind) => {
    for(const item of pools[kind]) {
      if (used.has(String(item.p.id))) continue;
      picked.push(item); used.add(String(item.p.id)); return true;
    }
    return false;
  };
  for (const [kind,quota] of [['amazon',2],['flipkart',2],['croma',1]]) {
    for(let i=0;i<quota && picked.length<max;i++) if (!take(kind)) break;
  }
  while(picked.length<max) {
    let added=false;
    for(const kind of ['amazon','flipkart','croma','other']) {
      if(picked.length>=max) break;
      if(take(kind))added=true;
    }
    if(!added)break;
  }
  // ProductRecommendationService returned its candidates in relevance order.
  // Keep this ordering within selected platform quotas; never sort on stale price.
  return picked.sort((a,b)=>a.i-b.i).map((x,i)=>({...x.p,rank:i+1}));
}
module.exports = { selectLiveBudgetTop };
