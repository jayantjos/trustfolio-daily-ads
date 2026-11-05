'use strict';
// This staged canary uses the production extraction functions without persisting
// their results or invoking the product-deletion path.
const fs=require('fs'), path=require('path'), Module=require('module'), assert=require('assert/strict');
const mongoose=require('mongoose');
const runtime=JSON.parse(require('child_process').execFileSync('pm2',['jlist'],{encoding:'utf8'}))
  .find(p=>p.name==='trustfolio-backend').pm2_env;
const env={...require('dotenv').parse(fs.readFileSync('.env')),...runtime};
for(const [key,value] of Object.entries(env)) {
  if(/^(BUDGET_|MAX_RANKING_|MAX_LEGACY_|FAST_TOP_|MAX_RECOMMENDATION_|LIVE_PRICE_|PRICE_WORKER_|CROMA_)/.test(key)) process.env[key]=String(value);
}
const uri=Object.entries(env).find(([key,value])=>/mongo/i.test(key)&&typeof value==='string'&&/^mongodb(\+srv)?:\/\//.test(value))?.[1];
if(!uri)throw new Error('Existing database binding unavailable');
const root=process.cwd();
function compile(source,name){
  const filename=path.join(root,'services',name), m=new Module(filename,module);
  m.filename=filename; m.paths=Module._nodeModulePaths(path.dirname(filename)); m._compile(source,filename); return m.exports;
}
(async()=>{
  await mongoose.connect(uri,{dbName:'trustfolio',autoIndex:false,autoCreate:false});
  const ranker=compile(STAGED_RANKER,'CanaryRanker.js');
  const campaign=compile(fs.readFileSync('services/LiveBudgetRecommendationService.js','utf8'),'CanaryCampaign.js');
  const service=compile(STAGED_SERVICE,'CanaryProgressive.js');
  const extraction=compile(fs.readFileSync('services/LivePriceService.js','utf8')+
    '\nmodule.exports.canary = {fetchLive,toLive,canFetchCroma,fetchCromaDirect};','CanaryExtraction.js');
  const collection=mongoose.connection.collection('my_products');
  const memory=new Map();
  let retailerCalls=0;
  const prices={async getLivePrices(ids){
    const docs=await collection.find({_id:{$in:ids.map(id=>new mongoose.Types.ObjectId(id))}}).toArray();
    return Promise.all(docs.map(async doc=>{
      const id=String(doc._id), prior=memory.get(id)||doc.live||{};
      const fresh=Date.now()-new Date(prior.checked_at||0).getTime()<=Number(process.env.LIVE_PRICE_FRESH_MS||60000);
      let live=prior;
      if(!fresh){
        const {canFetchCroma,fetchCromaDirect,fetchLive,toLive}=extraction.canary;
        const item=extraction.workerItem(doc);
        if(canFetchCroma(doc)||item){
          retailerCalls++;
          const result=await (canFetchCroma(doc)?fetchCromaDirect(doc):fetchLive(item)).catch(error=>({status:'error',error:error.message}));
          live=toLive(result,prior); memory.set(id,live);
        }
      }
      return {id,live,deleted:false};
    }));
  }};
  const queries=[['drones',20000,''],['smart-phones',12000,''],['smart-phones',20000,''],
    ['smart-phones',15000.5,''],['smart-phones',15000,'Samsung'],
    ['washing-machines',35000,''],['smart-tvs',20000,''],['laptops',60000,''],['smart-phones',15000,'']];
  const failures=[];
  for(const [category,budget,brand] of queries){
    const before=retailerCalls, start=Date.now();
    const result=await service.getTopProductsForCategoryAndBudget(category,budget,{brand},{ranker,prices,campaign});
    const ms=Date.now()-start;
    const summary={category,budget,brand,ms,retailerCalls:retailerCalls-before,...result};
    console.log('LIVE_CANARY',JSON.stringify(summary));
    try{
      assert.ok(ms<7500,'frontend latency gate exceeded');
      assert.ok(result.products.length>0,'no verified recommendations');
      assert.equal(new Set(result.products.map(p=>p.id)).size,result.products.length);
      assert.ok(result.products.every(p=>p.live_price_status==='ok'&&p.price_inr>0&&p.price_inr<=budget));
      if(category==='smart-phones'&&budget===15000&&!brand){
        assert.deepEqual(result.products.map(p=>p.id),['69f9e9f56529299d30426ac8','69f9ea1f6529299d30426ae4',
          '6a9e4a2e0933a0daedaddd80','6aa56d332bb194728fab44c3','6a2ed790ee20fca78fefdfde']);
      }else{
        assert.ok(result.products.every(p=>p.in_stock===true&&p.price_inr>=Math.ceil(Math.floor(budget)*0.5)));
        assert.ok(result.priceWindow.min>=Math.ceil(Math.floor(budget)*0.5));
      }
    }catch(error){failures.push({category,budget,brand,error:error.message});}
  }
  console.log('CANARY_SUMMARY',JSON.stringify({failures,retailerCalls,databaseWrites:0}));
  await mongoose.disconnect();
  if(failures.length)process.exitCode=1;
})().catch(async error=>{console.error(error.stack);await mongoose.disconnect();process.exitCode=1;});
