'use strict';
const {createRequire}=require('module');const local=createRequire(process.cwd()+'/package.json');
const mongoose=local('mongoose');local('dotenv').config();
const uri=['MONGODB_URI','MONGO_URI','MONGO_URL','MONGODB_URL','DB_URI','DATABASE_URL'].map(x=>process.env[x]).find(Boolean);
(async()=>{
 await mongoose.connect(uri,{dbName:'trustfolio',serverSelectionTimeoutMS:8000});
 const ids=['69f3543b1dafb58cccdbdfd0','69feec16fe6fd8dc386abcad'];
 const rows=await mongoose.connection.collection('my_products').find({_id:{$in:ids.map(x=>new mongoose.Types.ObjectId(x))}}).toArray();
 const service=local('./services/CromaLivePriceDirect');
 for(const d of rows){
  let output;
  try{output=await Promise.race([service.fetchCromaDirect(d),new Promise((_,rej)=>setTimeout(()=>rej(new Error('TIME_BUDGET')),25000))])}
  catch(e){output={status:'error',error:e?.message||'UNKNOWN'}}
  console.log('CROMA_20K_REAL_PRICE='+JSON.stringify({sku:d.platform_product_id,
   title:String(d.title||'').slice(0,95),
   catalogPrice:d.price_inr,latestDbStatus:d.live?.status||null,
   newStatus:output.status,priceNum:output.priceNum??null,
   error:output.error||null}));
 }
 console.log('CROMA_20K_TEST_MONGO_READ_ONLY=YES');
})().catch(e=>{console.log('CROMA_20K_TEST_ERROR='+String(e.name||'ERROR'))}).finally(()=>mongoose.disconnect());
