'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path');
const {getTopProductsForCategoryAndBudget:top}=require('./LiveBudgetRecommendationService');
for(const [category,budget,brand] of [['smart-phones',15000,''],['smart-phones',12000,''],['smart-phones',20000,''],['smart-phones',15000,'Samsung'],['washing-machines',15000,''],['smart-tvs',15000,''],['smart-phones',15000.5,'']]){
 test('ordinary live verification '+category+' '+budget+' '+brand,async()=>{
  let calls=0,options;const products=Array.from({length:5},(_,i)=>({id:'dynamic-'+i,price_inr:budget-100,title:'Catalog candidate '+i}));
  const result=await top(category,budget,{brand},{ranker:{async getTopProductsForCategoryAndBudget(c,b,o){options=o;return {products,priceWindow:{min:0,max:b},matchType:'within_budget'};}},prices:{async getLivePrices(ids){calls++;return ids.map(id=>({id,live:{status:'ok',in_stock:true,price_inr:budget-200}}));}}});
  assert.equal(calls,1);assert.equal(options.exactSmartphoneBudget,undefined);assert.deepEqual(result.products.map(p=>p.id),products.map(p=>p.id));assert.ok(result.products.every(p=>p.price_source==='website_live_price_api'&&!p.skip_live_price_check));assert.equal(result.livePriceRefreshCompleted,true);
 });
}
test('campaign IDs and bypass/cache flags absent from all four restored source files',()=>{
 for(const file of ['ProductController.js','ProductRecommendationService.js','LiveBudgetRecommendationService.js','ProductsTable.tsx']){
  const source=fs.readFileSync(path.join(__dirname,file),'utf8');
  for(const token of ['69f9e9f56529299d30426ac8','69f9ea1f6529299d30426ae4','6a9e4a2e0933a0daedaddd80','6aa56d332bb194728fab44c3','6a2ed790ee20fca78fefdfde','exactSmartphoneBudget','skip_live_price_check','catalog_not_live','exact-15000-v1'])assert.ok(!source.includes(token));
 }
});
