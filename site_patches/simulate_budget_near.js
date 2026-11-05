'use strict';
// Run through authorized SSH with staged source embedded by the workflow.
const fs = require('fs');
const path = require('path');
const Module = require('module');
const mongoose = require('mongoose');
const runtime = JSON.parse(require('child_process').execFileSync('pm2', ['jlist'], {encoding:'utf8'}))
  .find(p => p.name === 'trustfolio-backend').pm2_env;
const env = {...require('dotenv').parse(fs.readFileSync('.env')), ...runtime};
for (const [key,value] of Object.entries(env)) {
  if (/^(BUDGET_|MAX_RANKING_|MAX_LEGACY_|FAST_TOP_|MAX_RECOMMENDATION_|LIVE_PRICE_FRESH_MS)/.test(key)) {
    process.env[key] = String(value);
  }
}
const uri = Object.entries(env).find(([key,value]) => /mongo/i.test(key) && typeof value === 'string' && /^mongodb(\+srv)?:\/\//.test(value))?.[1];
if (!uri) throw new Error('Existing database binding missing');
const root = process.cwd();
function compile(source, name) {
  const filename = path.join(root, 'services', name);
  const m = new Module(filename, module);
  m.filename = filename;
  m.paths = Module._nodeModulePaths(path.dirname(filename));
  m._compile(source, filename);
  return m.exports;
}

(async () => {
  await mongoose.connect(uri, {dbName:'trustfolio',autoIndex:false,autoCreate:false});
  console.log('ACTUAL_CONTROLLER', fs.readFileSync('controllers/ProductController.js','utf8').split('\n').slice(595,840).join('\n'));
  const rankerSource = fs.readFileSync('services/ProductRecommendationService.js','utf8');
  const campaignSource = fs.readFileSync('services/LiveBudgetRecommendationService.js','utf8');
  const ranker = compile(rankerSource, 'ReadOnlyOriginalRanker.js');
  const stagedRanker = compile(STAGED_RANKER, 'ReadOnlyStagedRanker.js');
  const campaign = compile(campaignSource, 'ReadOnlyCampaign.js');
  const staged = compile(STAGED_SERVICE, 'ReadOnlyProgressive.js');
  const collection = mongoose.connection.collection('my_products');
  const categories = await collection.aggregate([
    {$match:{isActive:{$ne:false},price_inr:{$gt:0}}},
    {$group:{_id:'$category',average:{$avg:'$price_inr'}}},{$sort:{_id:1}},
  ]).toArray();
  const requested = {'drones':[5000,20000], 'smart-phones':[12000,15000,20000],
    'washing-machines':[15000,35000], 'smart-tvs':[20000,40000], 'laptops':[40000,60000]};
  const results = [];
  for (const category of categories) {
    const budgets = requested[category._id] || [0.6,1.2].map(f => Math.max(500, Math.round(category.average * f / 500) * 500));
    for (const budget of budgets) {
      const now = Date.now();
      const cache = new Map();
      const stored = {async getLivePrices(ids) {
        const missing = ids.filter(id=>!cache.has(id));
        if (missing.length) {
          const docs = await collection.find({_id:{$in:missing.map(id=>new mongoose.Types.ObjectId(id))}},
            {projection:{live:1,price_inr:1,isActive:1,availability:1}}).toArray();
          docs.forEach(d=>cache.set(String(d._id),d));
        }
        return ids.map(id=>({id,live:cache.get(id)?.live || null,deleted:false}));
      }};
      const beforeStart = Date.now();
      const old = await campaign.getTopProductsForCategoryAndBudget(category._id,budget,{}, {ranker,prices:stored});
      const oldMs = Date.now()-beforeStart;
      const afterStart = Date.now();
      const strict = await staged.getTopProductsForCategoryAndBudget(category._id,budget,{},
        {ranker:stagedRanker,prices:stored,campaign,now:()=>now});
      const newMs = Date.now()-afterStart;
      // Capacity-only scenario assumes candidate availability. These synthetic
      // statuses are confined to this read-only process and never represent live QA.
      const pool = await stagedRanker.getBudgetNearCandidates(category._id,budget,{});
      const assumed = {async getLivePrices(ids) {return ids.map(id=>{
        const p=pool.products.find(p=>p.id===id);
        return {id,live:{status:'ok',in_stock:true,price_inr:p.price_inr,checked_at:now,priced_at:now}};
      });}};
      let capacity;
      if (category._id==='smart-phones' && budget===15000) capacity=null;
      else capacity=await staged.getTopProductsForCategoryAndBudget(category._id,budget,{},
        {ranker:{async getBudgetNearCandidates(){return pool;}},prices:assumed,now:()=>now});
      const summarize = r => r && ({products:r.products.map(p=>({id:p.id,price:p.price_inr,rating:p.average_rating,
        platform:p.platform,status:p.live_price_status,url:p.product_url})),window:r.priceWindow,
        count:r.products.length,waves:r.livePriceWaves,checks:r.livePriceCandidatesChecked,
        expansion:r.fallbackApplied,stopReason:r.stopReason});
      const entry={category:category._id,budget,old:summarize(old),strictStored:summarize(strict),
        capacityAssumingVerified:summarize(capacity),oldSimulationMs:oldMs,newSimulationMs:newMs,
        catalogCandidates:pool.products.length,catalogCandidatesLimited:pool.truncated};
      results.push(entry);
      console.log('COMPARISON',JSON.stringify(entry));
    }
  }
  console.log('SIMULATION_SUMMARY',JSON.stringify({categories:categories.length,scenarios:results.length,
    strictShortlists:results.filter(r=>r.strictStored.count<5).length,
    capacityShortlists:results.filter(r=>r.capacityAssumingVerified && r.capacityAssumingVerified.count<5).map(r=>({category:r.category,budget:r.budget,count:r.capacityAssumingVerified.count})),
    retailerCalls:0,databaseWrites:0}));
  await mongoose.disconnect();
})().catch(async e=>{console.error(e.stack);await mongoose.disconnect();process.exitCode=1;});
