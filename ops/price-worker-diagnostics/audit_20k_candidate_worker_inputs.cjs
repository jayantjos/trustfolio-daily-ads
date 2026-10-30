'use strict';
const {createRequire}=require('module');const local=createRequire(process.cwd()+'/package.json');
const mongoose=local('mongoose');local('dotenv').config();
const uri=['MONGODB_URI','MONGO_URI','MONGO_URL','MONGODB_URL','DB_URI','DATABASE_URL'].map(x=>process.env[x]).find(Boolean);
(async()=>{
 await mongoose.connect(uri,{dbName:'trustfolio',serverSelectionTimeoutMS:9000});
 const ranker=local('./services/ProductRecommendationService');
 const {workerItem}=local('./services/LivePriceService');
 const {canFetchCroma}=local('./services/CromaLivePriceDirect');
 const col=mongoose.connection.collection('my_products');
 for(const category of ['smart-phones','washing-machines','headphones-earbuds']){
  let checked=[];
  for(let wave=0;wave<3;wave++){
   const rec=await ranker.getTopProductsForCategoryAndBudget(category,20000,{limit:5,excludeProductIds:checked});
   const found=(rec.products||[]).filter(x=>!checked.includes(String(x.id)));
   if(!found.length)break;
   checked.push(...found.map(x=>String(x.id)));
   const ids=found.map(x=>new mongoose.Types.ObjectId(x.id));
   const docs=await col.find({_id:{$in:ids}},{projection:{platform:1,platform_product_id:1,asin:1,original_product_url:1,clean_url:1,url:1,productUrl:1,price_inr:1,title:1,live:1}}).toArray();
   const byId=new Map(docs.map(x=>[String(x._id),x]));
   const rows=found.map(x=>{
    const d=byId.get(String(x.id));const item=d?workerItem(d):null;
    const platform=String(x.platform||'').toLowerCase();
    return {rank:x.rank||null,id:String(x.id),platform,title:String(x.title||'').slice(0,70),
      catalogPrice:x.price_inr,workerInput:item,
      cromaDirect:d?canFetchCroma(d):false,
      lastStatus:d?.live?.status||null,lastChecked:d?.live?.checked_at||null,
      lastPrice:d?.live?.price_inr??null,
      usable:platform==='croma'?(d?canFetchCroma(d):false):Boolean(item)};
   });
   console.log('RANKER_WORKER_20K_WAVE='+JSON.stringify({category,wave:wave+1,rows}));
  }
 }
 console.log('LIVE_STATUS_AUDIT_READ_ONLY=YES');
})().catch(e=>{console.log('AUDIT_ERROR='+String(e?.name||'error')+':'+String(e?.message||'').slice(0,150));process.exitCode=1}).finally(()=>mongoose.disconnect());
