'use strict';
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(process.argv[2], 'utf8');
const original = fs.readFileSync(process.argv[3], 'utf8');
function campaignBlock(text) {
  const start = text.indexOf('  if (options.exactSmartphoneBudget === true');
  assert.ok(start > 0);
  return text.slice(start, text.indexOf('\n  if (requestedBrand) {', start));
}
assert.equal(campaignBlock(source), campaignBlock(original));
const start = source.indexOf('async function getBudgetNearCandidates');
const end = source.indexOf('module.exports = {', start);
const products = [1,2,3,5,null].map((rating,i) => ({_id:String(i),rating,price_inr:19000,image:'valid'}));
products.push({_id:'no-image',rating:5,price_inr:19999});
const sandbox = {
  process,
  async fetchProductsInBudgetWindow(category,min,max,cap,options) {
    assert.equal(category,'drones'); assert.equal(min,10000); assert.equal(max,20000);
    assert.equal(options.candidateLimit,100);
    return {capped:products,totalMatches:products.length};
  },
  extractRating(p) {const n=parseFloat(p.rating);return n>0?n:null;},
  hasUsableProductImage(p) {return Boolean(p.image);},
  orderPickedByRatingThenSpecs(category,rows) {return [...rows].sort((a,b)=>(b.rating||0)-(a.rating||0));},
  resolveProductPrice(p) {return p.price_inr;},
  toProductDtos(rows) {return rows.map(p=>({id:p._id,price_inr:p.price_inr}));},
};
vm.createContext(sandbox);
vm.runInContext(source.slice(start,end) + '\nthis.get = getBudgetNearCandidates;',sandbox);
(async()=>{
  const result=await sandbox.get('drones',20000,{});
  assert.deepEqual(Array.from(result.products,p=>p.id),['3','2','4']);
  console.log('QUALITY_AND_CAMPAIGN_SOURCE_TESTS_PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
