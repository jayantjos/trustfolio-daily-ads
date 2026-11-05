'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),cp=require('child_process');
const root=process.cwd(),pkg=process.argv[2],mode=process.argv[3],mongoose=require('mongoose');
const runtime=JSON.parse(cp.execFileSync('pm2',['jlist'],{encoding:'utf8'})).find(p=>p.name==='trustfolio-backend').pm2_env;
const env={...require('dotenv').parse(fs.readFileSync('.env')),...runtime};
const uri=Object.values(env).find(v=>typeof v==='string'&&/^mongodb(\+srv)?:\/\//.test(v));
const ids=['69f9e9f56529299d30426ac8','69f9ea1f6529299d30426ae4','6a9e4a2e0933a0daedaddd80','6aa56d332bb194728fab44c3','6a2ed790ee20fca78fefdfde'];
let calls=0,writes=0;
for(const proto of [mongoose.Collection.prototype,mongoose.mongo.Collection.prototype])for(const method of ['insertOne','insertMany','updateOne','updateMany','replaceOne','deleteOne','deleteMany','findOneAndUpdate','findOneAndDelete','bulkWrite'])proto[method]=()=>{writes++;throw Error('Read-only evidence process');};
(async()=>{
 await mongoose.connect(uri,{dbName:'trustfolio',autoIndex:false,autoCreate:false});
 const ranker=require(path.join(root,'services/ProductRecommendationService'));
 const rec=await ranker.getTopProductsForCategoryAndBudget('smart-phones',15000,{limit:5,exactSmartphoneBudget:true});
 assert.deepEqual(rec.products.map(p=>p.id),ids);assert.ok(rec.products.every(p=>p.price_inr>0&&p.price_inr<=15000));
 if(mode==='before'){
  fs.writeFileSync(path.join(pkg,'catalog-before.json'),JSON.stringify(rec,null,2));
  console.log('BASELINE',JSON.stringify({products:rec.products.map(p=>({id:p.id,price:p.price_inr,url:p.product_url})),workerHost:new URL(env.PRICE_WORKER_URL).hostname,backendPort:Number(runtime.PORT||env.PORT||8081)}));
 }else{
  const before=JSON.parse(fs.readFileSync(path.join(pkg,'catalog-before.json')));
  assert.deepEqual(rec.products,before.products,'IDs, prices, fields, links and rank unchanged');
  const file=require.resolve(path.join(root,'services/LivePriceService'));
  require.cache[file]={id:file,filename:file,loaded:true,exports:{getLivePrices(){calls++;throw Error('Target must not invoke verification');}}};
  const helper=require(path.join(root,'services/LiveBudgetRecommendationService'));
  const result=await helper.getTopProductsForCategoryAndBudget('smart-phones',15000,{forceRefresh:true,useCache:false});
  assert.deepEqual(result.products.map(p=>p.id),ids);assert.equal(calls,0);assert.equal(writes,0);
  fs.writeFileSync(path.join(pkg,'deployed-call-proof.json'),JSON.stringify({livePriceCalls:calls,workerCallsViaLivePriceService:0,writes,ids},null,2));
  console.log('DEPLOYED_CALL_PROOF',JSON.stringify({livePriceCalls:calls,workerCallsViaLivePriceService:0,writes,ids}));
 }
 await mongoose.disconnect();
})().catch(e=>{console.error(e.stack);process.exit(1);});
