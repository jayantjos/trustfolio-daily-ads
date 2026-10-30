'use strict';
// Export QA-only *public product metadata*, not credentials or Mongo fields, for 100 each.
// DB read only. Rotate categories so broad product types are represented.
const {createRequire}=require('node:module');
const req=createRequire(process.cwd()+'/package.json');
const mongoose=req('mongoose');req('dotenv').config();
const uri=['MONGODB_URI','MONGO_URI','MONGO_URL','MONGODB_URL','DB_URI','DATABASE_URL'].map(k=>process.env[k]).find(Boolean);
const {workerItem}=req('./services/LivePriceService');
(async()=>{
 await mongoose.connect(uri,{dbName:'trustfolio',serverSelectionTimeoutMS:9000});
 const docs=await mongoose.connection.collection('my_products').find(
  {platform:{$in:['amazon','flipkart','croma']},price_inr:{$gte:250,$lte:150000}},
  {projection:{platform:1,platform_product_id:1,category:1,title:1,brand:1,product_url:1,original_product_url:1,price_inr:1,live:1}}
 ).sort({'live.checked_at':-1}).limit(12000).toArray();
 const groups={amazon:[],flipkart:[],croma:[]};
 const skipped={amazon:{},flipkart:{},croma:{}};
 for(const d of docs){
  const platform=d.platform; if(!groups[platform])continue;
  const id=String(d.platform_product_id||'').toUpperCase().trim();
  let input='',url='';
  if(platform==='amazon'){
   if(!/^B0[A-Z0-9]{8}$/.test(id)){skipped.amazon.invalid_identity=(skipped.amazon.invalid_identity||0)+1;continue;}
   input=id;url='https://www.amazon.in/dp/'+id;
  }else if(platform==='flipkart'){
   input=workerItem(d)||'';
   try {const u=new URL(input);if(!/^(?:www\.)?flipkart\.com$/i.test(u.hostname)||!u.searchParams.get('pid')||!u.pathname.includes('/p/itm'))throw Error();url=input;}
   catch(_){skipped.flipkart.invalid_identity=(skipped.flipkart.invalid_identity||0)+1;continue;}
  }else{
   if(!/^\d{4,12}$/.test(id)){skipped.croma.invalid_identity=(skipped.croma.invalid_identity||0)+1;continue;}
   url='https://www.croma.com/p/'+id;input=id;
  }
  groups[platform].push({platform,sku:id,category:String(d.category||'unknown').slice(0,35),
   title:String(d.title||'').slice(0,125),brand:String(d.brand||'').slice(0,50),
   stored_price:Number(d.price_inr)||null,url,input,
   last_live_status:d.live?.status||null,
   last_live_price:Number(d.live?.price_inr)||null});
 }
 const select=(rows)=>{
  const byCat=new Map();for(const r of rows){if(!byCat.has(r.category))byCat.set(r.category,[]);byCat.get(r.category).push(r)}
  const cats=[...byCat.keys()].sort();
  const sample=[],seen=new Set();
  let index=0;
  while(sample.length<100 && index<500){
   let added=0;
   for(const c of cats){const r=byCat.get(c)[index];if(r&&!seen.has(r.sku)){sample.push(r);seen.add(r.sku);added++}if(sample.length>=100)break;}
   if(added===0)break;index++;
  }
  return sample;
 };
 const selections=Object.fromEntries(Object.entries(groups).map(([k,v])=>[k,select(v)]));
 console.log('TF_100_QA_METADATA='+JSON.stringify({generated_at:new Date().toISOString(),
  target_per_platform:100,platforms:selections,valid_candidates:Object.fromEntries(Object.entries(groups).map(([k,v])=>[k,v.length])),skipped}));
 console.log('MONGO_READ_ONLY=YES');
})().catch(e=>{console.log('TF_QA_METADATA_ERROR='+String(e.name||'error'));process.exitCode=1}).finally(()=>mongoose.disconnect());
