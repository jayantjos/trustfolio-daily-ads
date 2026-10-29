'use strict';
require(process.cwd()+'/node_modules/dotenv').config();
const mongoose=require(process.cwd()+'/node_modules/mongoose');
const connectDB=require(process.cwd()+'/config/mongo');
const {workerItem}=require(process.cwd()+'/services/LivePriceService');
(async()=>{
 await connectDB();
 const col=mongoose.connection.collection('my_products');
 const docs=await col.find({
   platform:'flipkart','live.status':'ok',
   'live.checked_at':{$gte:new Date(Date.now()-7*86400000)}
 },{projection:{platform:1,title:1,platform_product_id:1,original_product_url:1,clean_url:1,url:1,productUrl:1,live:1}})
 .sort({'live.checked_at':-1}).limit(12).toArray();
 const chosen=docs.filter(d=>Boolean(workerItem(d))).slice(0,2);
 console.log('RECENT_FLIPKART_LIVE_SAMPLES='+chosen.length);
 const worker=String(process.env.PRICE_WORKER_URL||'').replace(/\/+$/,'');
 if(!worker){console.log('PRICE_WORKER_CONFIGURED=NO');return;}
 for(const d of chosen){
   const item=workerItem(d);
   try{
     const headers={'content-type':'application/json'};
     if(process.env.PRICE_WORKER_KEY)headers['x-api-key']=process.env.PRICE_WORKER_KEY;
     const res=await fetch(worker+'/api/check',{
       method:'POST',headers,
       body:JSON.stringify({items:[item],useCache:false}),
       signal:AbortSignal.timeout(9000)
     });
     const body=await res.json().catch(()=>null), v=body?.results?.[0]?.flipkart||null;
     console.log('FLIPKART_COMPARISON='+JSON.stringify({
       sku:d.platform_product_id,title:d.title?.slice(0,95),
       previous_live_status:d.live?.status,
       previous_live_price:d.live?.price_inr,
       worker_http:res.status, worker_status:v?.status||null,
       worker_price:v?.priceNum||null,store_http:v?.httpStatus||null,
       bytesRead:v?.bytesRead||null
     }));
   }catch(e){console.log('FLIPKART_COMPARISON_ERROR='+JSON.stringify({sku:d.platform_product_id,message:e.message}));}
 }
 console.log('MONGODB_WRITES=0');
})().catch(e=>{console.error('DIAGNOSTIC_ERROR='+e.message);process.exitCode=1}).finally(()=>mongoose.disconnect());
