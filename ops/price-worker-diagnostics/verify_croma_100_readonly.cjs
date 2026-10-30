'use strict';
const {createRequire}=require('node:module');const req=createRequire(process.cwd()+'/package.json');
const mongoose=req('mongoose');req('dotenv').config();
const uri=['MONGODB_URI','MONGO_URI','MONGO_URL','MONGODB_URL','DB_URI','DATABASE_URL'].map(x=>process.env[x]).find(Boolean);
const {fetchCromaDirect}=req('./services/CromaLivePriceDirect');
(async()=>{
 if(!uri)throw Error('MONGO_URI_NOT_FOUND');
 await mongoose.connect(uri,{dbName:'trustfolio',serverSelectionTimeoutMS:9000});
 const data=await mongoose.connection.collection('my_products').find({platform:'croma',price_inr:{$gte:250,$lte:150000}},
  {projection:{platform:1,platform_product_id:1,category:1,title:1,brand:1,product_url:1,original_product_url:1,price_inr:1,live:1}}
 ).sort({'live.checked_at':-1}).limit(4500).toArray();
 const groups=new Map();for(const d of data){
  if(!/^\d{4,12}$/.test(String(d.platform_product_id||'')))continue;
  const cat=String(d.category||'unknown');
  if(!groups.has(cat))groups.set(cat,[]);groups.get(cat).push(d);
 }
 const targets=[],seen=new Set(),categories=[...groups.keys()].sort();
 for(let i=0;i<300&&targets.length<100;i++){
  for(const cat of categories){
   const d=groups.get(cat)[i];
   if(d&&!seen.has(d.platform_product_id)){targets.push(d);seen.add(d.platform_product_id)}
   if(targets.length===100)break;
  }
 }
 console.log('CROMA_100_SELECTED='+targets.length);
 let at=0;const rows=new Array(targets.length);
 await Promise.all(Array.from({length:3},async()=>{
  for(;;){
   const j=at++;if(j>=targets.length)return;
   const d=targets[j],start=Date.now();
   let x;
   try{x=await fetchCromaDirect(d)}catch(e){x={status:'error',error:String(e.name||'request_error')}}
   const price=x?.status==='ok'&&Number.isFinite(x.priceNum)?x.priceNum:null;
   rows[j]={platform:'croma',category:String(d.category||'unknown'),sku:String(d.platform_product_id||''),
    title:String(d.title||'').slice(0,135),brand:String(d.brand||'').slice(0,50),
    url:/^https?:\/\//.test(d.product_url||'')?d.product_url:'https://www.croma.com/p/'+d.platform_product_id,
    stored_price:Number(d.price_inr)||null,live_price:price,
    status:x?.status||'error',error:x?.error||null,elapsed_ms:Date.now()-start,
    last_live_status:d.live?.status||null};
   console.log('CROMA_100_RESULT='+JSON.stringify(rows[j]));
  }
 }));
 console.log('CROMA_100_SUMMARY='+JSON.stringify({tested:rows.length,ok:rows.filter(x=>x.live_price!==null).length,
   no_price:rows.filter(x=>x.live_price===null).length,changed:rows.filter(x=>x.live_price!==null&&x.live_price!==x.stored_price).length,
   read_only:true}));
 console.log('PRODUCTION_MONGO_WRITES=ZERO');
})().catch(e=>{console.log('CROMA_100_RUN_ERROR='+String(e?.name||'error')+':'+String(e?.message||'').slice(0,180));process.exitCode=1}).finally(()=>mongoose.disconnect());
