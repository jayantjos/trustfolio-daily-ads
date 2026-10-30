'use strict';
const {createRequire}=require('module');
const appRequire=createRequire(process.cwd()+'/package.json');
const mongoose=appRequire('mongoose');appRequire('dotenv').config();
const uri=['MONGODB_URI','MONGO_URI','MONGO_URL','MONGODB_URL','DB_URI','DATABASE_URL'].map(k=>process.env[k]).find(Boolean);
(async()=>{
 if(!uri)throw Error('mongo_env_missing');
 await mongoose.connect(uri,{serverSelectionTimeoutMS:9000});
 const c=mongoose.connection.client.db('trustfolio').collection('my_products');
 const rows=await c.find({platform:'croma', platform_product_id:{$regex:'^[0-9]{4,12}$'}},
 {projection:{platform_product_id:1,title:1,brand:1,price_inr:1,live:1,product_url:1}}).limit(300).toArray();
 const selected=rows.filter(d=>d.live?.status==='ok'&&d.live?.price_inr>0).slice(0,5);
 console.log('CROMA_TEST_CANDIDATES='+JSON.stringify(selected.map(d=>({
  sku:String(d.platform_product_id),title:String(d.title||'').slice(0,100),
  brand:String(d.brand||''),lastLivePrice:d.live.price_inr,checkedAt:d.live.checked_at
 }))));
 console.log('READ_ONLY=YES');
})().catch(e=>{console.log('CROMA_SAMPLE_ERROR='+String(e.name||'error'));process.exitCode=1}).finally(()=>mongoose.disconnect());
