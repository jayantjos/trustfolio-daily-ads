'use strict';
// Read-only price mismatch investigation: no Mongo writes or product deletion.
require(process.cwd()+'/node_modules/dotenv').config();
const mongoose=require(process.cwd()+'/node_modules/mongoose');
const connectDB=require(process.cwd()+'/config/mongo');
const {workerItem}=require(process.cwd()+'/services/LivePriceService');
const fields={_id:1,platform:1,title:1,brand:1,platform_product_id:1,asin:1,
 price_inr:1,price:1,currentPriceValue:1,live:1,
 product_url:1,original_product_url:1,clean_url:1,url:1,productUrl:1};
const shortURL=(value)=>{
  if(!value)return null;
  try { const u=new URL(String(value)); return {host:u.hostname,path:u.pathname.slice(0,120),pid:u.searchParams.get('pid'),lid:u.searchParams.get('lid')}; }
  catch(e){return {invalid:true,length:String(value).length}}
};
(async()=>{
 await connectDB();
 const col=mongoose.connection.collection('my_products');
 const docs=await col.find({platform:{$regex:'flipkart', $options:'i'},title:{$regex:'POCO X8 Pro Max', $options:'i'}},
  {projection:fields}).limit(16).toArray();
 console.log('POCO_MATCHES='+docs.length);
 for(const d of docs){
   const supported=workerItem(d);
   console.log('POCO_PRODUCT='+JSON.stringify({
     id:String(d._id), title:d.title, sku:d.platform_product_id,
     stored_price_inr:d.price_inr,price:d.price,currentPriceValue:d.currentPriceValue,
     live:d.live?{status:d.live.status,price_inr:d.live.price_inr,checked_at:d.live.checked_at,
      priced_at:d.live.priced_at,error:d.live.error,availability:d.live.availability}:null,
     worker_item:supported,
     worker_supported:Boolean(supported),
     urls:Object.fromEntries(['product_url','original_product_url','clean_url','url','productUrl'].map(k=>[k,shortURL(d[k])]))
   }));
 }
 const target=docs.find(d=>/blue/i.test(d.title||'')&&/512\s*gb/i.test(d.title||''));
 if (!target) {console.log('EXACT_BLUE_512_SKU_NOT_FOUND=YES');return;}
 const item=workerItem(target);
 if (!item) {console.log('ROOT_CAUSE_WORKER_ITEM_NULL=YES');return;}
 const workerUrl=String(process.env.PRICE_WORKER_URL||'').replace(/\/+$/,'');
 if(!workerUrl){console.log('WORKER_NOT_CONFIGURED=YES');return;}
 const headers={'content-type':'application/json'};
 if(process.env.PRICE_WORKER_KEY)headers['x-api-key']=process.env.PRICE_WORKER_KEY;
 for(const cache of [true,false]){
   const start=Date.now();
   try {
     const res=await fetch(workerUrl+'/api/check',{
       method:'POST',headers,
       body:JSON.stringify({items:[item],useCache:cache}),
       signal:AbortSignal.timeout(11000)
     });
     const data=await res.json().catch(()=>null);
     const result=data?.results?.[0]||null;
     console.log('FLIPKART_WORKER_DIAGNOSTIC='+JSON.stringify({
       useCache:cache,http_status:res.status,elapsed_ms:Date.now()-start,
       firstResult:result,error:data?.error||null,
       WARNING:'Worker read only; no Mongo writes'
     }).slice(0,2500));
   }catch(e){console.log('FLIPKART_WORKER_EXCEPTION='+JSON.stringify({useCache:cache,
     message:e.message,elapsed_ms:Date.now()-start}));}
 }
 console.log('MONGODB_WRITES=0');
})().catch(e=>{console.error('AUDIT_ERROR='+e.message);process.exitCode=1}).finally(()=>mongoose.disconnect());
