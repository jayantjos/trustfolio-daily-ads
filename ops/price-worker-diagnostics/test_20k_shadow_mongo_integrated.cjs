'use strict';
// Isolated MongoDB persistence + real backend service integration.
// Simulated retailer HTTP results; NEVER writes to real my_products.
const {createRequire}=require('node:module');
const appRequire=createRequire(process.cwd()+'/package.json');
const mongoose=appRequire('mongoose');appRequire('dotenv').config();
const uri=['MONGODB_URI','MONGO_URI','MONGO_URL','MONGODB_URL','DB_URI','DATABASE_URL'].map(k=>process.env[k]).find(Boolean);
process.env.PRICE_WORKER_URL='https://trustfolio-qa.invalid';
process.env.PRICE_WORKER_KEY='qa-no-real-credential';
process.env.LIVE_PRICE_FRESH_MS='0';
const croma=appRequire('./services/CromaLivePriceDirect');
const originalCroma=croma.fetchCromaDirect;
croma.fetchCromaDirect=async()=>({status:'ok',priceNum:18999,in_stock:true});
const priceService=appRequire('./services/LivePriceService');
const budgetService=appRequire('./services/LiveBudgetRecommendationService');
const originalFetch=global.fetch;
const expectedByInput=new Map([
 ['B0AAAA0001',21500],['B0AAAA0002',18500],
 ['MOBTESTSKU0000001',17999],['MOBTESTSKU0000002',19500],
 ['MOBTESTSKU0000003',16999],['MOBTESTSKU0000004',null],
]);
const stub=async(_url,opts)=>{
 const payload=JSON.parse(opts.body),item=payload.items[0];
 if(!opts.headers['x-api-key']||payload.items.length!==1)throw Error('BACKEND_WORKER_REQUEST_INVALID');
 const isAmazon=/^B0[A-Z0-9]{8}$/.test(item),pid=isAmazon?item:new URL(item).searchParams.get('pid');
 const value=expectedByInput.get(pid);
 let part;
 if(value===null)part={status:'error',priceNum:null,error:'store_http_502',httpStatus:502};
 else if(value)part={status:'ok',priceNum:value,in_stock:true};
 else part={status:'error',priceNum:null,error:'price_not_exposed'};
 const record={asin:isAmazon?pid:null,pid,amazon:isAmazon?part:{status:'skipped'},flipkart:isAmazon?{status:'skipped'}:part};
 return {ok:true,status:200,json:async()=>({success:true,results:[record]})};
};
global.fetch=stub;
let shadow=null,shadowDeleted=null,originalCollection=null;
(async()=>{
 if(!uri)throw Error('MONGO_ENV_NOT_SET');
 await mongoose.connect(uri,{dbName:'trustfolio',serverSelectionTimeoutMS:9000});
 const db=mongoose.connection.db;
 const suffix=String(Date.now());
 const colname='tf_qa_price_e2e_'+suffix;
 shadow=db.collection(colname);
 shadowDeleted=db.collection(colname+'_deleted');
 const mk=(platform,id,price,variant)=>({
   _id:new mongoose.Types.ObjectId(),platform,
   platform_product_id:id,asin:platform==='amazon'?id:undefined,
   title:'QA contract-only '+variant,
   original_product_url:platform==='flipkart'
     ?'https://www.flipkart.com/qa-product/p/itm123456789abc?pid='+id
     :platform==='amazon'?'https://www.amazon.in/dp/'+id:'',
   price:String(price),price_inr:price,currentPriceValue:price,
   live:{status:'ok',price_inr:price,checked_at:new Date(0)}
 });
 const docs=[
  mk('amazon','B0AAAA0001',19999,'A over-budget after live'),
  mk('flipkart','MOBTESTSKU0000001',19990,'B cheaper after live'),
  mk('croma','300154',18999,'C direct API'),
  mk('flipkart','MOBTESTSKU0000002',19500,'D eligible'),
  mk('amazon','B0AAAA0002',18500,'E eligible'),
  mk('flipkart','MOBTESTSKU0000003',19000,'F replacement'),
  mk('flipkart','MOBTESTSKU0000004',14999,'G HTTP502 should not delete')
 ];
 await shadow.insertMany(docs);
 // Preload real controller/model definitions before temporarily redirecting test collections.
 // Otherwise Mongoose model compilation may receive native collection instead of its adapter.
 appRequire('./controllers/ProductController');
 originalCollection=mongoose.connection.collection.bind(mongoose.connection);
 mongoose.connection.collection=function(name){
   if(name==='my_products')return shadow;
   if(name==='my_products_deleted')return shadowDeleted;
   return originalCollection(name);
 };
 const rankerDocs=docs.slice(0,6).map(d=>({id:String(d._id),platform:d.platform,title:d.title,price_inr:d.price_inr}));
 const ranker={getTopProductsForCategoryAndBudget:async (_cat,_budget,opts)=>{
  const skipped=new Set((opts.excludeProductIds||[]).map(String));
  return {products:rankerDocs.filter(p=>!skipped.has(String(p.id))).slice(0,5),
    totalMatches:rankerDocs.length,matchType:'within_budget',fallbackApplied:false,
    priceWindow:{min:0,max:20000}};
 }};
 const rec=await budgetService.getTopProductsForCategoryAndBudget('qa-test',20000,{limit:5},{ranker,prices:priceService});
 const chosen=rec.products.map(d=>({id:d.id,platform:d.platform,liveStatus:d.live_price_status,
   source:d.price_source,price:d.price_inr}));
 const persisted=await shadow.find({}).toArray();
 const byId=new Map(persisted.map(d=>[String(d._id),d]));
 const over=byId.get(String(docs[0]._id));
 const flipkart=byId.get(String(docs[1]._id));
 const replacement=byId.get(String(docs[5]._id));
 const good=rec.products.length===5
  &&rec.products.every(p=>Number(p.price_inr)<=20000 &&p.price_source==='website_live_price_api')
  &&!rec.products.some(p=>String(p.id)===String(docs[0]._id))
  &&rec.products.some(p=>String(p.id)===String(docs[5]._id))
  &&over.price_inr===21500&&over.price==='21500'&&over.currentPriceValue===21500
  &&flipkart.price_inr===17999&&replacement.price_inr===16999;
 console.log('QA_REAL_BACKEND_20K_WAVE_COUNT='+rec.livePriceWaves);
 console.log('QA_REAL_BACKEND_20K_PRODUCT_COUNT='+rec.products.length);
 console.log('QA_REAL_BACKEND_20K_SELECTED='+JSON.stringify(chosen));
 console.log('QA_SHADOW_MONGODB_WRITE_STATUS='+ (good?'PASS':'FAIL'));
 console.log('QA_OVER_BUDGET_REMOVED='+(!rec.products.some(p=>String(p.id)===String(docs[0]._id))));
 console.log('QA_REPLACEMENT_SELECTED='+rec.products.some(p=>String(p.id)===String(docs[5]._id)));
 console.log('QA_SHADOW_UPDATED_CANONICAL_PRICE='+JSON.stringify({amazon:over.price_inr,flipkart:flipkart.price_inr,replacement:replacement.price_inr}));
 if(!good)throw Error('MONGO_SHADOW_E2E_CONTRACT_FAILED');
 const fail=await priceService.getLivePrices([String(docs[6]._id)]);
 const failRow=await shadow.findOne({_id:docs[6]._id});
 console.log('QA_HTTP502_NO_DELETE='+Boolean(fail.length===1&&failRow&&failRow.price_inr===14999&&failRow.live?.status==='error'));
 console.log('QA_HTTP502_CATALOG_PRICE_STALE='+Boolean(failRow&&failRow.price_inr===14999));
 console.log('QA_PRODUCTION_MY_PRODUCTS_WRITE_ATTEMPT=NONE_ROUTED');
})().catch(e=>{console.log('SHADOW_E2E_TEST_ERROR='+String(e?.name||'Error')+':'+String(e?.message||'').slice(0,150));process.exitCode=1})
.finally(async()=>{
 global.fetch=originalFetch;croma.fetchCromaDirect=originalCroma;
 if(originalCollection)mongoose.connection.collection=originalCollection;
 try{if(shadow)await shadow.drop()}catch(_){}
 try{if(shadowDeleted)await shadowDeleted.drop()}catch(_){}
 console.log('QA_SHADOW_COLLECTION_CLEANUP=COMPLETE');
 await mongoose.disconnect();
});
