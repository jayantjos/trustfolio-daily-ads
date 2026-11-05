'use strict';
const fs = require('node:fs');
const assert = require('node:assert/strict');
const source = fs.readFileSync(process.argv[2], 'utf8');
const anchor = source.indexOf('const exactSmartphoneBudgetKey');
assert.ok(anchor > 0);
const start = source.lastIndexOf('const brandKey', anchor);
const end = source.indexOf('\nif (brand)', anchor);
assert.ok(start > 0 && end > anchor);
const get = new Function('normalizedCategory', 'budget', 'limit', 'brand',
  'topProductsResponseCache', 'topProductsResponseCacheTtlMs', 'res',
  source.slice(start,end) + '\nreturn {key:topCacheKey};');
const cache = new Map();
const invoke = (category, budget, brand='') => get(category,budget,5,brand,cache,()=>30000,{json:v=>v});
const campaign = invoke('smart-phones',15000).key;
assert.equal(campaign,'cat-guard-live-budget-v1|smart-phones|exact-15000-v1|5|');
const keys = [campaign,invoke('drones',15000).key,invoke('smart-phones',15000.5).key,
  invoke('smart-phones',15000.7).key,invoke('smart-phones',15000,'Samsung').key];
assert.equal(new Set(keys).size,5);
const key = invoke('drones',20000).key;
cache.set(key,{at:Date.now(),value:{data:{priceVerificationExpiresAt:Date.now()-1}}});
assert.equal(invoke('drones',20000).key,key);
const sentinel={data:{priceVerificationExpiresAt:Date.now()+10000}};
cache.set(key,{at:Date.now(),value:sentinel});
assert.equal(invoke('drones',20000),sentinel);
console.log('REAL_CONTROLLER_CACHE_TESTS_PASS');
