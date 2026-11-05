'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { getTopProductsForCategoryAndBudget: top } = require('./BudgetNearRecommendationService');
const NOW = 1793850000000;
const product = (id, price, platform = 'amazon') => ({ id, price_inr: price, platform, product_url: 'https://store.test/' + id });
const good = price => ({ status: 'ok', price_inr: price, in_stock: true, checked_at: NOW, priced_at: NOW });

function fixture(products, overrides = {}) {
  const calls = [];
  return { calls, dependencies: {
    now: () => NOW,
    ranker: { async getBudgetNearCandidates() { return { products }; } },
    prices: { async getLivePrices(ids) {
      calls.push(ids);
      return ids.map(id => ({ id, live: overrides[id] || good(products.find(p => p.id === id).price_inr) }));
    } },
  } };
}

test('A: five in initial window preserve quality order and links', async () => {
  const products = [19999,19800,19500,19300,19000].map((p,i) => product(String(i),p));
  const f = fixture(products), r = await top('drones',20000,{},f.dependencies);
  assert.deepEqual(r.products.map(p => p.id),products.map(p => p.id));
  assert.equal(r.livePriceWaves,1); assert.equal(r.fallbackApplied,false);
  r.products.forEach(p => assert.equal(p.product_url,'https://store.test/' + p.id));
});

test('B,K: three first-window products retained when two require 80 percent', async () => {
  const f = fixture([19999,19000,18000,17500,16000].map((p,i)=>product(String(i),p)));
  const r = await top('drones',20000,{},f.dependencies);
  assert.deepEqual(r.products.map(p=>p.id),['0','1','2','3','4']);
  assert.equal(r.livePriceWaves,2); assert.equal(r.fallbackApplied,true);
  assert.deepEqual(r.priceWindow,{min:16000,max:20000}); assert.equal(r.totalMatches,5);
});

test('C,D,O: sparse drones stops at 50 percent with fewer results', async () => {
  for (const products of [[product('1',19999)], [product('1',4942)]]) {
    const f = fixture(products), r = await top('drones',20000,{},f.dependencies);
    assert.equal(r.products.length,products[0].price_inr===19999 ? 1 : 0);
    assert.equal(r.priceWindow.min,10000); assert.equal(r.livePriceWaves,5);
    assert.equal(r.stopReason,'minimum_window_reached');
  }
});

test('E,F,G,H: over-budget, unavailable, timeout and expired caches never qualify', async () => {
  const products = ['over','oos','timeout','expired','nostock'].map(id=>product(id,19000));
  const f = fixture(products, {
    over: good(20001), oos: {...good(19000),status:'out_of_stock'},
    timeout: {...good(19000),status:'error',error:'timeout'},
    expired: {...good(19000),priced_at:NOW-60001}, nostock:{...good(19000),in_stock:false},
  });
  const r = await top('drones',20000,{},f.dependencies);
  assert.equal(r.products.length,0); assert.equal(f.calls.flat().length,5);
});

test('I: duplicate candidates across windows are checked only once',async()=>{
  const p = product('same',17000), f = fixture([p,p,p]);
  const r = await top('drones',20000,{},f.dependencies);
  assert.equal(r.products.length,1); assert.deepEqual(f.calls,[['same']]);
});

test('J: diversity cannot displace a product in a closer budget band',async()=>{
  const f = fixture([product('a',19999),product('b',19800),product('c',19700),product('d',18000,'flipkart')]);
  const r = await top('drones',20000,{limit:3},f.dependencies);
  assert.deepEqual(r.products.map(p=>p.id),['a','b','c']);
});

test('J: diversity is a soft preference within the same budget band',async()=>{
  const f = fixture([product('a',19999),product('b',19800),product('c',19700),product('d',19600,'flipkart')]);
  const r = await top('drones',20000,{limit:4},f.dependencies);
  assert.deepEqual(r.products.map(p=>p.id),['a','b','d','c']);
});

test('live price moving down waits for the appropriate expansion without recheck',async()=>{
  const f = fixture([product('a',19000)],{a:good(14500)});
  const r = await top('drones',20000,{},f.dependencies);
  assert.equal(r.products[0].price_inr,14500); assert.equal(f.calls.length,1);
  assert.equal(r.fallbackApplied,true);
});

test('L: exact campaign delegates the original budget and dependencies unchanged',async()=>{
  const sentinel = { campaign:true }, dependencies = {campaign:{async getTopProductsForCategoryAndBudget(c,b,o,d){
    assert.equal(c,'smart-phones'); assert.equal(b,15000); assert.equal(d,dependencies); return sentinel;
  }}};
  assert.equal(await top('smart-phones',15000,{},dependencies),sentinel);
});

for (const [category,budget,brand] of [['smart-phones',15000,'Samsung'],['smart-phones',15000.5,''],['smart-phones',12000,''],['smart-phones',20000,''],['washing-machines',20000,''],['smart-tvs',20000,''],['laptops',20000,'']]) {
  test('M,N,P: automatic '+category+' '+budget+' '+brand,async()=>{
    const f=fixture([product('a',Math.floor(budget))]);
    const r=await top(category,budget,{brand},f.dependencies);
    assert.equal(r.selectionPolicy,'progressive-budget-near-v1');
    assert.equal(r.originalBudget,budget); assert.equal(r.products.length,1);
  });
}

test('bounded checks, accurate stopping metadata and maximum batch of two',async()=>{
  const products=Array.from({length:100},(_,i)=>product(String(i),19000));
  const f=fixture(products,Object.fromEntries(products.map(p=>[p.id,{status:'error'}])));
  const r=await top('drones',20000,{},f.dependencies);
  assert.equal(r.livePriceCandidatesChecked,10); assert.equal(r.stopReason,'candidate_limit');
  assert.ok(f.calls.every(ids=>ids.length<=2));
});

test('slow verification stops additional batches',async()=>{
  const f=fixture(Array.from({length:12},(_,i)=>product(String(i),19000)));
  let time=NOW;
  f.dependencies.now=()=>time;
  f.dependencies.prices={async getLivePrices(ids){time+=6000;return ids.map(id=>({id,live:{status:'error'}}));}};
  const r=await top('drones',20000,{},f.dependencies);
  assert.equal(r.livePriceBatches,2); assert.equal(r.stopReason,'time_budget');
});

test('request deadline returns safely even if verification remains pending',async()=>{
  const f=fixture([product('a',19000)]);
  let ticks=0;
  f.dependencies.now=()=>ticks++===0 ? NOW : NOW+6495;
  f.dependencies.prices={async getLivePrices(){return new Promise(()=>{});}};
  const r=await top('drones',20000,{},f.dependencies);
  assert.equal(r.products.length,0);
  assert.equal(r.livePriceBatches,1);
  assert.equal(r.stopReason,'time_budget');
  assert.equal(r.verificationFailures.timeout,1);
});

test('Q: concurrent equal requests coalesce while category, brand and budget stay isolated',async()=>{
  let queries=0;
  const m={exports:{}};
  const sandbox={module:m,exports:m.exports,process,Date,Map,Set,setTimeout,clearTimeout,require(name){
    if(name.includes('ProductRecommendation'))return {async getBudgetNearCandidates(){queries++;await new Promise(r=>setImmediate(r));return {products:[]};}};
    if(name.includes('LivePrice'))return {};
    throw new Error(name);
  }};
  vm.runInNewContext(fs.readFileSync(require.resolve('./BudgetNearRecommendationService'),'utf8'),sandbox);
  const get=m.exports.getTopProductsForCategoryAndBudget;
  await Promise.all([get('drones',20000),get('drones',20000),get('drones',20000.5),get('drones',20000,{brand:'X'}),get('washing-machines',20000)]);
  assert.equal(queries,4);
  await get('drones',20000); assert.equal(queries,5);
});

test('invalid, duplicate and incomplete verification IDs fail closed',async()=>{
  for(const rows of [[],[{id:'other'}],[{id:'a'},{id:'a'}]]){
    const f=fixture([product('a',19000)]);
    f.dependencies.prices={async getLivePrices(){return rows;}};
    await assert.rejects(top('drones',20000,{},f.dependencies),/IDs/);
  }
});
