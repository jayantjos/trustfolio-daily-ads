'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const top = require('./LiveBudgetRecommendationService').getTopProductsForCategoryAndBudget;
const IDS = ['69f9e9f56529299d30426ac8','69f9ea1f6529299d30426ae4','6a9e4a2e0933a0daedaddd80',
  '6aa56d332bb194728fab44c3','6a2ed790ee20fca78fefdfde'];
const PRODUCTS = IDS.map((id,i)=>({id,price_inr:14000,product_url:'https://retailer.test/'+id,rank:i+1}));
function fixture(overrides={}) {
  const calls=[];
  return {calls,dependencies:{
    ranker:{async getTopProductsForCategoryAndBudget(category,budget,options){
      return {products:PRODUCTS.filter(p=>!options.excludeProductIds.includes(p.id)),totalMatches:5};
    }},
    prices:{async getLivePrices(ids){
      calls.push(ids);
      return ids.map(id=>({id,live:{status:'ok',in_stock:true,price_inr:14000,...overrides[id]}}));
    }},
  }};
}

test('exact campaign verifies one listing at a time and preserves all five IDs, prices and links',async()=>{
  const f=fixture(),r=await top('smart-phones',15000,{},f.dependencies);
  assert.deepEqual(f.calls,IDS.map(id=>[id]));
  assert.deepEqual(r.products.map(p=>p.id),IDS);
  assert.deepEqual(r.products.map(p=>p.rank),[1,2,3,4,5]);
  r.products.forEach(p=>{assert.equal(p.price_inr,14000);assert.equal(p.product_url,'https://retailer.test/'+p.id);});
});

test('failed, unavailable, over-budget and explicitly false stock never fabricate campaign eligibility',async()=>{
  const f=fixture({[IDS[1]]:{status:'error',error:'timeout'},[IDS[2]]:{status:'out_of_stock'},
    [IDS[3]]:{price_inr:15001},[IDS[4]]:{in_stock:false}});
  const r=await top('smart-phones',15000,{},f.dependencies);
  assert.deepEqual(r.products.map(p=>p.id),[IDS[0]]);
  assert.deepEqual(f.calls,IDS.map(id=>[id]));
});

for(const [category,budget,brand] of [['smart-phones',12000,''],['smart-phones',20000,''],
  ['smart-phones',15000.5,''],['smart-phones',15000,'Samsung'],['drones',20000,''],['washing-machines',35000,'']]) {
  test('normal verification batching remains unchanged '+category+' '+budget+' '+brand,async()=>{
    const f=fixture();
    await top(category,budget,{brand},f.dependencies);
    assert.deepEqual(f.calls,[IDS]);
  });
}

test('concurrent exact requests share one verification job while normal requests remain independent',async()=>{
  const module={exports:{}};
  let priceCalls=0,active=0,maxActive=0;
  const f=fixture();
  const prices={async getLivePrices(ids){
    priceCalls++;active++;maxActive=Math.max(maxActive,active);
    await new Promise(resolve=>setImmediate(resolve));
    active--;
    return ids.map(id=>({id,live:{status:'ok',in_stock:true,price_inr:14000}}));
  }};
  vm.runInNewContext(fs.readFileSync(require.resolve('./LiveBudgetRecommendationService'),'utf8'),{
    module,exports:module.exports,Map,Set,require(name){
      if(name.includes('ProductRecommendation'))return f.dependencies.ranker;
      if(name.includes('LivePrice'))return prices;
      throw new Error(name);
    },
  });
  const get=module.exports.getTopProductsForCategoryAndBudget;
  const [a,b]=await Promise.all([get('smart-phones',15000),get('smart-phones',15000)]);
  assert.equal(a,b);assert.equal(priceCalls,5);assert.equal(maxActive,1);
  await get('smart-phones',15000);assert.equal(priceCalls,10);
  await Promise.all([get('drones',20000),get('drones',20000)]);
  assert.equal(priceCalls,12);assert.equal(maxActive,2);
});

test('coalescing clears a rejected job so a later valid request can recover',async()=>{
  const module={exports:{}};
  let fail=true;
  const f=fixture();
  vm.runInNewContext(fs.readFileSync(require.resolve('./LiveBudgetRecommendationService'),'utf8'),{
    module,exports:module.exports,Map,Set,require(name){
      if(name.includes('ProductRecommendation'))return f.dependencies.ranker;
      if(name.includes('LivePrice'))return {async getLivePrices(ids){
        if(fail)throw new Error('controlled transient failure');
        return ids.map(id=>({id,live:{status:'ok',in_stock:true,price_inr:14000}}));
      }};
      throw new Error(name);
    },
  });
  const get=module.exports.getTopProductsForCategoryAndBudget;
  await assert.rejects(get('smart-phones',15000),/controlled transient failure/);
  fail=false;
  assert.equal((await get('smart-phones',15000)).products.length,5);
});
