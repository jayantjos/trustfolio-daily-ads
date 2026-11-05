'use strict';
const fs=require('fs'),assert=require('assert/strict');
const pkg=process.argv[2],base=process.argv[3]||'https://api.trustfolio.in';
const before=JSON.parse(fs.readFileSync(pkg+'/catalog-before.json'));
(async()=>{
 const results=[];
 for(const suffix of ['','&forceRefresh=true&useCache=false','&forceRefresh=true']){
  const start=Date.now(),r=await fetch(base+'/api/products/top?category=smart-phones&budget=15000&limit=5'+suffix,{signal:AbortSignal.timeout(15000)}),body=await r.json();
  assert.equal(r.status,200);assert.equal(body.success,true);const data=body.data;
  assert.equal(data.count,5);assert.deepEqual(data.products.map(p=>p.id),before.products.map(p=>p.id));
  data.products.forEach((p,i)=>{for(const key of Object.keys(before.products[i]))assert.deepEqual(p[key],before.products[i][key],'Preserve '+key);assert.equal(p.skip_live_price_check,true);assert.equal(p.live_price_status,'not_checked');});
  assert.equal(data.livePriceRefreshCompleted,false);assert.equal(data.livePriceCandidatesChecked,0);assert.equal(data.priceVerificationStatus,'catalog_not_live');
  results.push({ms:Date.now()-start,body});
 }
 fs.writeFileSync(pkg+'/production-api-after.json',JSON.stringify(results,null,2));
 console.log('PRODUCTION_API_PASS',JSON.stringify({latencies:results.map(r=>r.ms),products:results[0].body.data.products.map(p=>({id:p.id,price:p.price_inr})),livePriceCandidatesChecked:0,priceVerificationStatus:'catalog_not_live'}));
})().catch(e=>{console.error(e.stack);process.exit(1);});
