'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { getTopProductsForCategoryAndBudget: getTop } = require('./LiveBudgetRecommendationService');

function fake(catalog, prices, log) {
  return {
    ranker: {
      async getTopProductsForCategoryAndBudget(category, budget, options) {
        log.push({ category, budget, excludes: options.excludeProductIds });
        const products = catalog.filter(x => !options.excludeProductIds.includes(x.id)).slice(0, 5);
        return { products, totalMatches: catalog.length,
          priceWindow: { min: Math.floor(budget * 0.9), max: budget },
          matchType: products.length ? 'within_budget' : 'none', fallbackApplied: false };
      },
    },
    prices: {
      async getLivePrices(ids) {
        return ids.map(id => ({ id, ...prices[id] }));
      },
    },
  };
}
function product(id, price = 29999) {
  return { id, rank: Number(id.slice(1)), title: id, price_inr: price, brand: 'LG',
    platform: 'amazon', average_rating: 4.5 };
}

test('over-budget live price is excluded and next ranked MongoDB product fills slot', async () => {
  const log = [];
  const data = ['p1','p2','p3','p4','p5','p6','p7'].map(id => product(id));
  const live = Object.fromEntries(data.map(x => [x.id, { live: { status: 'ok', price_inr: 30000 } }]));
  live.p2.live.price_inr = 36000;
  const result = await getTop('washing-machines', 35000, { limit: 5 }, fake(data, live, log));
  assert.deepEqual(result.products.map(p => p.id), ['p1','p3','p4','p5','p6']);
  assert.equal(result.products.every(p => p.price_inr <= 35000), true);
  assert.deepEqual(result.products.map(p => p.rank), [1,2,3,4,5]);
  assert.ok(log[1].excludes.includes('p2'));
  assert.equal(result.livePriceCandidatesChecked, 7);
});

test('out of stock is removed and replacement preserves original candidate order', async () => {
  const arr = Array.from({length: 8}, (_, i) => product('p' + (i + 1)));
  const states = Object.fromEntries(arr.map(p => [p.id, {live:{status:'ok',price_inr: 32000},deleted:false}]));
  states.p1.deleted = true;
  states.p4.live.status = 'out_of_stock';
  const result=await getTop('washing-machines', 35000, {}, fake(arr, states, []));
  assert.deepEqual(result.products.map(p=>p.id),['p2','p3','p5','p6','p7']);
  assert.equal(result.livePriceRefreshCompleted,true);
});

test('stale fallback is only shown within budget, and higher catalog candidates are skipped', async () => {
  const arr = Array.from({length: 7}, (_, i) => product('p' + (i+1), 33500));
  arr[1].price_inr=38000;
  const states=Object.fromEntries(arr.map(p=>[p.id,{live:{status:'blocked',price_inr:900},deleted:false}]));
  const r=await getTop('washing-machines',35000,{},fake(arr,states,[]));
  assert.deepEqual(r.products.map(p=>p.id),['p1','p3','p4','p5','p6']);
  assert.equal(r.products.every(p=>p.price_source==='website_catalog'),true);
});

test('wrong or incomplete refreshed ID sets cause a controlled failure',async()=>{
  const arr=Array.from({length:5},(_,i)=>product('p'+(i+1)));
  await assert.rejects(getTop('washing-machines',35000,{},{
    ranker:fake(arr,{},[]).ranker,
    prices:{async getLivePrices(){return [{id:'other',live:null}];}},
  }),/mismatched IDs/);
  await assert.rejects(getTop('washing-machines',35000,{},{
    ranker:fake(arr,{},[]).ranker,
    prices:{async getLivePrices(){return [];}},
  }),/incomplete IDs/);
});

test('less than five verified products never pads with fake ones',async()=>{
  const arr=[product('p1'),product('p2')];
  const states=Object.fromEntries(arr.map(p=>[p.id,{live:{status:'ok',price_inr:33000}}]));
  const r=await getTop('washing-machines',35000,{},fake(arr,states,[]));
  assert.equal(r.products.length,2);
  assert.deepEqual(r.products.map(p=>p.id),['p1','p2']);
});
