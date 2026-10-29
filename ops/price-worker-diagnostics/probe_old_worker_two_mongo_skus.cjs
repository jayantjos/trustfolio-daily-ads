'use strict';
/* Read-only signed old Worker price checks for TWO known genuine Mongo records. */
const {createRequire}=require('node:module');
const appRequire=createRequire(process.cwd()+'/package.json');
const mongoose=appRequire('mongoose');
appRequire('dotenv').config();
const url=process.env.PRICE_WORKER_URL;
const key=process.env.PRICE_WORKER_KEY;
const uri=['MONGODB_URI','MONGO_URI','MONGO_URL','MONGODB_URL','DB_URI','DATABASE_URL'].map(k=>process.env[k]).find(Boolean);
const pids=['MOBHQFDZKKM7EEFZ','MOBH2AHZH779MGYF'];
(async()=>{
 if(!uri||!url||!key){console.log('WORKER_BASELINE_CONFIG_MISSING');return;}
 await mongoose.connect(uri,{serverSelectionTimeoutMS:8000});
 const coll=mongoose.connection.client.db('trustfolio').collection('my_products');
 const docs=await coll.find({platform:'flipkart',platform_product_id:{$in:pids}}).toArray();
 const workerItem=appRequire('./services/LivePriceService').workerItem;
 const arr=docs.map(d=>({id:d.platform_product_id,stored:d.price_inr,item:workerItem(d)})).filter(d=>d.item);
 console.log('MONGO_WORKER_ITEM_FORMAT='+JSON.stringify(arr.map(d=>({id:d.id,fields:Object.keys(d.item),url:String(d.item.url||d.item.link||'').slice(0,160)}))));
 if(!arr.length)return;
 const target=url.replace(/\/+$/,'')+'/api/check';
 const response=await fetch(target,{
   method:'POST',headers:{'content-type':'application/json','x-api-key':key},
   body:JSON.stringify({items:arr.map(x=>x.item),useCache:false}),signal:AbortSignal.timeout(24000)
 });
 const body=await response.json();
 console.log('OLD_WORKER_HTTP='+response.status);
 for(let i=0;i<arr.length;i++){
   const result=body?.results?.[i]||{};
   const m=result.flipkart||result.Flipkart||{};
   console.log('OLD_WORKER_REAL_PRICE='+JSON.stringify({pid:arr[i].id,status:m.status,priceNum:m.priceNum,
     httpStatus:m.httpStatus,bytesRead:m.bytesRead,error:m.error||null,cached:result.cached}));
 }
 console.log('OLD_WORKER_BASELINE_READ_ONLY=YES');
})().catch(e=>{console.log('OLD_WORKER_PROBE_ERROR='+String(e?.name||'error')+':'+String(e?.message||'').slice(0,150));process.exitCode=1}).finally(()=>mongoose.disconnect());
