'use strict';
const assert=require('node:assert/strict');
const cp=require('node:child_process');
let active=0, peak=0, total=0;
cp.execFile = function(program,args,opts,cb) {
  assert.equal(program,'curl');
  total++;
  active++;
  peak=Math.max(peak,active);
  // Mock only: avoid real API traffic while validating parallel queue behavior.
  setTimeout(()=>{
    active--;
    cb(null,JSON.stringify({products:[{
      code:'317463',
      price:{priceType:'BUY',value:33900},
      pincodePrice:{priceType:'BUY',value:33900}
    }]}),'');
  },35);
};
const {canFetchCroma,fetchCromaDirect}=require('./CromaLivePriceDirect');
(async()=>{
  const base={platform:'croma',platform_product_id:'317463',title:'Apple Watch SE 3 GPS+Cellular with Starlight Sport Band',brand:'Apple'};
  assert.equal(canFetchCroma(base),true);
  const count=30;
  const results=await Promise.all(Array.from({length:count},()=>fetchCromaDirect({...base})));
  assert.equal(results.length,count);
  assert.ok(results.every(x=>x.status==='ok' && x.priceNum===33900 && x.in_stock===null));
  assert.equal(total,count);
  assert.equal(peak,8,'expected 8 parallel curl calls');
  assert.equal(active,0);
  console.log('CROMA_SIMULATED_REQUESTS='+total);
  console.log('CROMA_PEAK_PARALLEL='+peak);
  console.log('CROMA_30_ITEM_QUEUE_TEST=PASS');
  console.log('REAL_CROMA_REQUESTS=0');
})().catch(e=>{console.error(e);process.exitCode=1;});
