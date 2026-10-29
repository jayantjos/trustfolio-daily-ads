'use strict';
// Read-only Amazon SKU selection for automated Cloudflare Worker tests.
const {createRequire}=require('module');
const appRequire=createRequire(process.cwd()+'/package.json');
const mongoose=appRequire('mongoose');appRequire('dotenv').config();
const uri=['MONGODB_URI','MONGO_URI','MONGO_URL','MONGODB_URL','DB_URI','DATABASE_URL'].map(k=>process.env[k]).find(Boolean);
(async()=>{
  if(!uri)throw Error('mongo_config_missing');
  await mongoose.connect(uri,{serverSelectionTimeoutMS:9000});
  const c=mongoose.connection.client.db('trustfolio').collection('my_products');
  const docs=await c.find({platform:'amazon','live.status':'ok'},
    {projection:{platform_product_id:1,asin:1,title:1,price_inr:1,live:1,product_url:1}})
    .sort({'live.checked_at':-1}).limit(100).toArray();
  const candidates=docs.map(d=>{
    const source=[d.platform_product_id,d.asin,/\/(?:dp|gp\/product)\/([A-Z0-9]{10})/i.exec(String(d.product_url||''))?.[1]];
    const asin=source.map(x=>String(x||'').toUpperCase()).find(x=>/^[A-Z0-9]{10}$/.test(x));
    return asin?{asin,title:String(d.title||'').slice(0,90),lastLive:Number(d.live?.price_inr)||null,lastChecked:d.live?.checked_at||null}:null;
  }).filter(Boolean).slice(0,5);
  console.log('AMAZON_LIVE_SAMPLE='+JSON.stringify(candidates));
  console.log('MONGODB_READ_ONLY=YES');
})().catch(e=>{console.log('AUDIT_ERROR='+String(e.name||'error'));process.exitCode=1}).finally(()=>mongoose.disconnect());
