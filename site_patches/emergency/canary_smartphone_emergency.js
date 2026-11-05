'use strict';
// Read-only live canary. Production extraction functions are reused without
// invoking their persistence or deletion paths.
const fs = require('fs');
const path = require('path');
const Module = require('module');
const assert = require('assert/strict');
const mongoose = require('mongoose');
const runtime = JSON.parse(require('child_process').execFileSync('pm2',['jlist'],{encoding:'utf8'}))
  .find(p=>p.name==='trustfolio-backend').pm2_env;
const env = {...require('dotenv').parse(fs.readFileSync('.env')), ...runtime};
for (const [key,value] of Object.entries(env)) {
  if (/^(PRICE_WORKER_|LIVE_PRICE_|CROMA_)/.test(key)) process.env[key]=String(value);
}
const uri = Object.entries(env).find(([key,value])=>/mongo/i.test(key)&&typeof value==='string'&&/^mongodb(\+srv)?:\/\//.test(value))?.[1];
if (!uri) throw new Error('Existing database binding missing');
function compile(source,name) {
  const filename=path.join(process.cwd(),'services',name);
  const module=new Module(filename);
  module.filename=filename;
  module.paths=Module._nodeModulePaths(path.dirname(filename));
  module._compile(source,filename);
  return module.exports;
}

(async()=>{
  await mongoose.connect(uri,{dbName:'trustfolio',autoIndex:false,autoCreate:false});
  const candidate=compile(CANDIDATE_SOURCE,'EmergencyCampaignCanary.js');
  const extract=compile(fs.readFileSync('services/LivePriceService.js','utf8')+
    '\nmodule.exports.canary={fetchLive,toLive};','EmergencyPriceExtractionCanary.js');
  const collection=mongoose.connection.collection('my_products');
  const freshness=Number(env.LIVE_PRICE_FRESH_MS||60000);
  const evidence=[];
  let cacheHits=0,requests=0,active=0,maxActive=0;
  const prices={async getLivePrices(ids){
    const docs=await collection.find({_id:{$in:ids.map(id=>new mongoose.Types.ObjectId(id))}}).toArray();
    const rows=[];
    for (const doc of docs) {
      let live=doc.live||{};
      const checked=new Date(live.checked_at||0).getTime();
      if (Date.now()-checked>freshness) {
        requests++; active++; maxActive=Math.max(maxActive,active);
        const start=Date.now();
        const result=await extract.canary.fetchLive(extract.workerItem(doc))
          .catch(error=>({status:'error',error:error.message}));
        active--;
        live=extract.canary.toLive(result,live);
        evidence.push({id:String(doc._id),status:live.status,error:live.error,price:live.price_inr,ms:Date.now()-start});
      } else { cacheHits++; }
      rows.push({id:String(doc._id),live,deleted:false});
      const priced=new Date(live.priced_at||0).getTime();
      if (live.status==='ok' && !(priced>0 && Date.now()-priced<=freshness)) {
        throw new Error('Expired verified price for '+String(doc._id));
      }
    }
    return rows;
  }};
  const start=Date.now();
  const result=await candidate.getTopProductsForCategoryAndBudget('smart-phones',15000,{}, {
    ranker:require('./services/ProductRecommendationService'),prices,
  });
  const elapsedMs=Date.now()-start;
  console.log('EMERGENCY_CANARY',JSON.stringify({elapsedMs,requests,cacheHits,maxActive,evidence,result}));
  const ids=['69f9e9f56529299d30426ac8','69f9ea1f6529299d30426ae4','6a9e4a2e0933a0daedaddd80','6aa56d332bb194728fab44c3','6a2ed790ee20fca78fefdfde'];
  assert.deepEqual(result.products.map(p=>p.id),ids,'Campaign eligibility gate');
  assert.deepEqual(result.products.map(p=>p.rank),[1,2,3,4,5]);
  assert.ok(result.products.every(p=>p.live_price_status==='ok'&&p.price_inr>0&&p.price_inr<=15000));
  assert.ok(maxActive<=1);
  assert.ok(elapsedMs<7800,'Frontend request latency gate');
  console.log('EMERGENCY_CANARY_PASS');
  await mongoose.disconnect();
})().catch(async error=>{console.error(error.stack);await mongoose.disconnect();process.exitCode=1;});
