'use strict';
/* TrustFolio READ-ONLY catalog sample audit, no private variables printed.
   Run from ~/apps/trustfolio/node-backend with node <this script>. */
const mongoose=require('mongoose');
require('dotenv').config();
const dburi=['MONGODB_URI','MONGO_URI','MONGO_URL','MONGODB_URL','DB_URI','DATABASE_URL'].map(k=>process.env[k]).find(Boolean);
const pids=['MOBH2AHZH779MGYF','MOBHQFDZKKM7EEFZ','MOBHH2KYWG8UBBAF'];
const brief=doc=>({
  mongoId:String(doc._id),platform:doc.platform,title:String(doc.title||'').slice(0,130),
  knownPid:doc.platform_product_id||doc.product_id||doc.flipkart_pid||doc.pid||null,
  url:String(doc.product_url||doc.url||'').split('?')[0].slice(0,160),
  price_inr:Number(doc.price_inr||doc.currentPriceValue||doc.price)||null,
  live_status:doc.live?.status||null,live_price:doc.live?.price_inr||null,
  checked_at:doc.live?.checked_at||null,
  // Never print any env values
});
(async()=>{
 if(!dburi){console.log('MONGO_CONNECTION_CONFIG=NOT_FOUND');process.exitCode=2;return;}
 await mongoose.connect(dburi,{serverSelectionTimeoutMS:9000});
 const db=mongoose.connection.client.db('trustfolio');
 const coll=db.collection('my_products');
 const known=await coll.find({platform:'flipkart', $or:[
   {platform_product_id:{$in:pids}},{product_id:{$in:pids}},
   {pid:{$in:pids}},
   ...pids.map(pid=>({product_url:{$regex:pid,$options:'i'}}))
 ]},{projection:{platform:1,title:1,platform_product_id:1,product_id:1,flipkart_pid:1,pid:1,product_url:1,url:1,price_inr:1,currentPriceValue:1,price:1,live:1}}).limit(10).toArray();
 console.log('KNOWN_FLIPKART_MONGO='+JSON.stringify(known.map(brief)));
 const fresh=await coll.find({platform:'flipkart',price_inr:{$gte:10000,$lte:90000},product_url:{$regex:'flipkart.com'}},
 {projection:{platform:1,title:1,platform_product_id:1,product_id:1,flipkart_pid:1,pid:1,product_url:1,url:1,price_inr:1,currentPriceValue:1,price:1,live:1}}).sort({'live.checked_at':-1}).limit(8).toArray();
 console.log('RECENT_FLIPKART_CANDIDATES='+JSON.stringify(fresh.map(brief)));
 console.log('MONGO_READ_ONLY=YES');
})().catch(e=>{console.log('MONGO_AUDIT_ERROR='+String(e?.message||e).replace(/mongodb(?:\+srv)?:\/\/\S+/gi,'[REDACTED]').slice(0,220));process.exitCode=1}).finally(()=>mongoose.disconnect());
