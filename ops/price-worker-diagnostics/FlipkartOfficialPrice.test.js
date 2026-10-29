'use strict';
const assert=require('node:assert/strict');
const {fetchFlipkartOfficial,parseProduct,sameVariant}=require('./FlipkartOfficialPrice');
const doc={platform:'flipkart',title:'POCO X8 Pro Max (Blue, 512 GB)',platform_product_id:'MOBHH2KYWG8UBBAF'};
const base={productId:doc.platform_product_id,title:doc.title,
  flipkartSellingPrice:{amount:49999,currency:'INR'},
  flipkartSpecialPrice:{amount:47349,currency:'INR'},
  maximumRetailPrice:{amount:61999,currency:'INR'},inStock:true};
const live=parseProduct({productBaseInfoV1:base},doc);
assert.equal(live?.status,'ok');assert.equal(live.priceNum,49999);
assert.equal(live.in_stock,true);
assert.equal(parseProduct({productBaseInfoV1:{...base,productId:'MOBHMGG5SQZQXZF9'}},doc),null);
assert.equal(parseProduct({productBaseInfoV1:{...base,title:'POCO X8 Pro Max (White, 512 GB)'}},doc),null);
assert.equal(parseProduct({productBaseInfoV1:{...base,title:'POCO X8 Pro Max (Blue, 256 GB)'}},doc),null);
assert.equal(parseProduct({productBaseInfoV1:{...base,flipkartSellingPrice:null}},doc),null);
assert.equal(parseProduct({productBaseInfoV1:{...base,flipkartSellingPrice:{amount:49999,currency:'USD'}}},doc),null);
assert.equal(parseProduct({productBaseInfoV1:{...base,inStock:false}},doc).status,'not_available');
assert.equal(sameVariant(doc.title,doc.title),true);
let calls=0;
(async()=>{
 const missing=await fetchFlipkartOfficial(doc,{env:{},fetch:()=>{calls++;throw Error('should not call');}});
 assert.equal(missing,null);assert.equal(calls,0);
 const ok=await fetchFlipkartOfficial(doc,{
   env:{FLIPKART_AFFILIATE_ID:'testID',FLIPKART_AFFILIATE_TOKEN:'testToken'},
   fetch:async(url,opts)=>{
      calls++;
      assert.match(url,/id=MOBHH2KYWG8UBBAF/);
      assert.equal(opts.headers['Fk-Affiliate-Id'],'testID');
      return {ok:true,json:async()=>({productBaseInfoV1:base})};
   }
 });
 assert.equal(ok.priceNum,49999);assert.equal(calls,1);
 const unauthorized=await fetchFlipkartOfficial(doc,{
   env:{FLIPKART_AFFILIATE_ID:'testID',FLIPKART_AFFILIATE_TOKEN:'testToken'},
   fetch:async()=>({ok:false,status:401})
 });
 assert.equal(unauthorized,null);
 console.log('OFFICIAL_FLIPKART_PID_VARIANT_PRICE_TEST=PASS');
 console.log('MRP_BANK_OFFER_EXCLUDED=PASS');
 console.log('UNCONFIGURED_WORKER_FALLBACK_TEST=PASS');
 console.log('NO_LIVE_API_CALLS_WITHOUT_CREDENTIALS=PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
