'use strict';
// LIVE MongoDB/Ranker READ ONLY: uses same ranker as production, never getLivePrices.
const {createRequire}=require('module');
const appRequire=createRequire(process.cwd()+'/package.json');
const mongoose=appRequire('mongoose');appRequire('dotenv').config();
const uri=['MONGODB_URI','MONGO_URI','MONGO_URL','MONGODB_URL','DB_URI','DATABASE_URL'].map(k=>process.env[k]).find(Boolean);
const ranker=appRequire('./services/ProductRecommendationService');
(async()=>{
 if(!uri) throw Error('MONGODB_URI_NOT_FOUND');
 await mongoose.connect(uri,{serverSelectionTimeoutMS:9000});
 const col=mongoose.connection.client.db('trustfolio').collection('my_products');
 const groups=await col.aggregate([
  {$match:{price_inr:{$gt:0,$lte:20000},platform:{$in:['flipkart','amazon','croma']}}},
  {$group:{_id:{category:'$category',platform:'$platform'},count:{$sum:1}}},
  {$sort:{count:-1}},{$limit:60}
 ]).toArray();
 console.log('MONGO_20K_PLATFORM_CATEGORIES='+JSON.stringify(groups.slice(0,30)));
 const categoryGroups={};
 for(const g of groups){
  const name=String(g._id.category||'').trim();
  if(!name)continue;
  (categoryGroups[name]??={})[g._id.platform]=g.count;
 }
 const choices=Object.entries(categoryGroups).filter(([k,v])=>['amazon','flipkart','croma'].every(p=>(v[p]||0)>0));
 console.log('ALL_THREE_20K_CATEGORIES='+JSON.stringify(choices.slice(0,12)));
 console.log('MONGOOSE_DEFAULT_DB_NAME='+mongoose.connection.name);
 console.log('MONGOOSE_DEFAULT_DB_CATALOG_COUNT='+await mongoose.connection.collection('my_products').estimatedDocumentCount());
 const categories=['smartwatches','headphones-earbuds','ceiling-fans','smart-phones','washing-machines','speakers'];
 const summarize=r=>({id:String(r.id||''),platform:r.platform,title:String(r.title||'').slice(0,90),price_inr:r.price_inr,rank:r.rank,brand:r.brand,product_url:String(r.product_url||r.url||'').slice(0,160)});
 for(const category of categories){
  try{
   const rec=await ranker.getTopProductsForCategoryAndBudget(category,20000,{limit:5});
   console.log('RANKER_20K_RESPONSE='+JSON.stringify({category,productCount:rec.products?.length||0,totalMatches:rec.totalMatches,products:(rec.products||[]).map(summarize)}));
  }catch(e){console.log('RANKER_CATEGORY_ERROR='+JSON.stringify({category,error:String(e?.message||e).slice(0,90)}))}
 }

 console.log('RANKER_DB_MUTATION=NONE');
})().catch(e=>{console.log('RANKER_AUDIT_ERROR='+String(e?.name||'error')+':'+String(e?.message||'').replace(/mongodb(?:\+srv)?:\/\/\S+/ig,'[REDACTED]').slice(0,150));process.exitCode=1}).finally(()=>mongoose.disconnect());
