'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {getTopProductsForCategoryAndBudget: top} = require('./LiveBudgetRecommendationService');
const ids = ['69f9e9f56529299d30426ac8','69f9ea1f6529299d30426ae4','6a9e4a2e0933a0daedaddd80',
  '6aa56d332bb194728fab44c3','6a2ed790ee20fca78fefdfde'];
const products = ids.map((id,i)=>({id,rank:i+1,price_inr:14000+i,title:'Existing '+id,
  specifications:{RAM:'4 GB'},main_image:'https://images.test/'+id,product_url:'https://retailer.test/'+id}));
function fixture() {
  const calls=[];
  return {calls,dependencies:{
    ranker:{async getTopProductsForCategoryAndBudget(category,budget,opts){
      calls.push({kind:'ranker',category,budget,opts});
      return {products:products.filter(p=>!(opts.excludeProductIds||[]).includes(p.id)),totalMatches:5,
        priceWindow:{min:0,max:budget},matchType:'within_budget'};
    }},
    prices:{async getLivePrices(list){
      calls.push({kind:'prices',ids:list});
      return list.map(id=>({id,live:{status:'ok',in_stock:true,price_inr:11000}}));
    }},
  }};
}

test('exact unbranded campaign uses existing ranker and database values with zero verification',async()=>{
  const f=fixture(),r=await top('smart-phones',15000,{},f.dependencies);
  assert.equal(f.calls.length,1);
  assert.equal(f.calls[0].opts.exactSmartphoneBudget,true);
  assert.deepEqual(r.products.map(p=>p.id),ids);
  assert.deepEqual(r.products.map(p=>p.rank),[1,2,3,4,5]);
  r.products.forEach((p,i)=>{
    for(const field of ['price_inr','title','specifications','main_image','product_url']) assert.deepEqual(p[field],products[i][field]);
    assert.equal(p.price_source,'website_catalog');
    assert.equal(p.live_price_status,'not_checked');
    assert.equal(p.skip_live_price_check,true);
  });
  assert.equal(r.livePriceVerificationSkipped,true);
  assert.equal(r.livePriceRefreshCompleted,false);
  assert.equal(r.livePriceCandidatesChecked,0);
});

test('forceRefresh, useCache false and missing Worker never defeat the server bypass',async()=>{
  for(const failure of ['HTTP 503','timeout','unreachable']){
    const f=fixture();
    Object.defineProperty(f.dependencies,'prices',{get(){throw new Error('Must not access prices '+failure);}});
    const r=await top('smart-phones','15000',{forceRefresh:true,useCache:false},f.dependencies);
    assert.equal(r.products.length,5);assert.equal(f.calls.length,1);
  }
});

test('a changed database price is used immediately without hardcoded campaign prices',async()=>{
  const f=fixture();
  f.dependencies.ranker={async getTopProductsForCategoryAndBudget(){return {products:products.map(p=>({...p,price_inr:12345}))};}};
  const r=await top('smart-phones',15000,{},f.dependencies);
  assert.ok(r.products.every(p=>p.price_inr===12345));
});

for(const [category,budget,brand] of [['smart-phones',12000,''],['smart-phones',20000,''],
  ['smart-phones',15000.5,''],['smart-phones',14999.99,''],['smart-phones',15000,'Samsung'],
  ['washing-machines',15000,''],['smart-tvs',15000,'']]){
  test('live verification retained '+category+' '+budget+' '+brand,async()=>{
    const f=fixture();
    const r=await top(category,budget,{brand},f.dependencies);
    assert.equal(f.calls.filter(c=>c.kind==='prices').length,1);
    assert.equal(r.livePriceRefreshCompleted,true);
    assert.ok(r.products.every(p=>p.price_inr===11000&&p.price_source==='website_live_price_api'));
    assert.notEqual(r.livePriceVerificationSkipped,true);
  });
}

test('catalog cache namespace rejects old live response and keeps other keys unchanged',()=>{
  const source=fs.readFileSync(path.join(__dirname,'ProductController.js'),'utf8');
  const anchor=source.indexOf('const exactSmartphoneBudgetKey');
  const start=source.lastIndexOf('const brandKey',anchor);
  const end=source.indexOf('\nif (brand)',anchor);
  assert.ok(start>0&&end>start);
  const fn=new Function('normalizedCategory','budget','limit','brand','topProductsResponseCache','topProductsResponseCacheTtlMs','res',
    source.slice(start,end)+'\nreturn {key:topCacheKey};');
  const cache=new Map();
  const get=(category,budget,brand='')=>fn(category,budget,5,brand,cache,()=>30000,{json:x=>x});
  cache.set('cat-guard-live-budget-v1|smart-phones|exact-15000-v1|5|',{at:Date.now(),value:{oldLive:true}});
  assert.equal(get('smart-phones',15000).key,'cat-guard-catalog-15000-v1|smart-phones|exact-15000-v1|5|');
  assert.equal(get('smart-phones',12000).key,'cat-guard-live-budget-v1|smart-phones|12000|5|');
  assert.equal(get('smart-phones',15000,'Samsung').key,'cat-guard-live-budget-v1|smart-phones|exact-15000-v1|5|samsung');
});

test('the target path does not even import LivePriceService',async()=>{
  const f=fixture(),m={exports:{}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'LiveBudgetRecommendationService.js'),'utf8'),{
    module:m,exports:m.exports,require(name){
      if(name.includes('ProductRecommendation'))return f.dependencies.ranker;
      throw new Error('Forbidden target dependency '+name);
    },
  });
  const r=await m.exports.getTopProductsForCategoryAndBudget('smart-phones',15000);
  assert.equal(r.products.length,5);
});
