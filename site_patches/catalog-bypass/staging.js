'use strict';
// Isolated process: real production controller, ranker and MongoDB reads; all writes and verification forbidden.
const fs=require('fs'),path=require('path'),Module=require('module'),assert=require('assert/strict'),http=require('http');
const root=process.cwd(),pkg=process.argv[2],mongoose=require('mongoose');
const runtime=JSON.parse(require('child_process').execFileSync('pm2',['jlist'],{encoding:'utf8'})).find(p=>p.name==='trustfolio-backend').pm2_env;
const env={...require('dotenv').parse(fs.readFileSync('.env')),...runtime};
const uri=Object.values(env).find(v=>typeof v==='string'&&/^mongodb(\+srv)?:\/\//.test(v));
if(!uri)throw Error('Existing MongoDB binding missing');
let writes=0,calls=0,workerCalls=0;
const forbidden=()=>{writes++;throw Error('Staging MongoDB write forbidden');};
for(const proto of [mongoose.Collection.prototype,mongoose.mongo.Collection.prototype])for(const name of ['insertOne','insertMany','updateOne','updateMany','replaceOne','deleteOne','deleteMany','findOneAndUpdate','findOneAndReplace','findOneAndDelete','bulkWrite'])proto[name]=forbidden;
for(const name of ['http','https']){const module=require(name);const original=module.request;module.request=function(...args){workerCalls++;throw Error('Staging outbound retailer request forbidden');};}
const ids=['69f9e9f56529299d30426ac8','69f9ea1f6529299d30426ae4','6a9e4a2e0933a0daedaddd80','6aa56d332bb194728fab44c3','6a2ed790ee20fca78fefdfde'];
function compile(relative,source){const filename=path.join(root,relative),m=new Module(filename);m.filename=filename;m.paths=Module._nodeModulePaths(path.dirname(filename));m._compile(source,filename);require.cache[filename]=m;return m.exports;}
(async()=>{
 await mongoose.connect(uri,{dbName:'trustfolio',autoIndex:false,autoCreate:false});
 const collection=mongoose.connection.collection('my_products');
 const docs=await collection.find({_id:{$in:ids.map(id=>new mongoose.Types.ObjectId(id))}}).toArray();
 assert.equal(docs.length,5);
 const ranker=require(path.join(root,'services/ProductRecommendationService'));
 const baseline=await ranker.getTopProductsForCategoryAndBudget('smart-phones',15000,{limit:5,exactSmartphoneBudget:true});
 assert.deepEqual(baseline.products.map(p=>p.id),ids);
 const pricesFile=require.resolve(path.join(root,'services/LivePriceService'));
 require.cache[pricesFile]={id:pricesFile,filename:pricesFile,loaded:true,exports:{async getLivePrices(list){calls++;return list.map(id=>({id,live:{status:'error',error:'simulated timeout'}}));}}};
 compile('services/LiveBudgetRecommendationService.js',fs.readFileSync(path.join(pkg,'LiveBudgetRecommendationService.js'),'utf8'));
 const controller=compile('controllers/ProductController.js',fs.readFileSync(path.join(pkg,'ProductController.js'),'utf8'));
 const server=http.createServer((req,res)=>{const query=Object.fromEntries(new URL(req.url,'http://localhost').searchParams);const adapter={status(n){res.statusCode=n;return this;},json(v){res.setHeader('Content-Type','application/json');res.end(JSON.stringify(v));return this;}};controller.getTopProducts({query},adapter);});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 async function request(query){const start=Date.now();const response=await fetch('http://127.0.0.1:'+server.address().port+'/api/products/top?'+query);const body=await response.json();assert.equal(response.status,200,JSON.stringify(body));return {body,ms:Date.now()-start};}
 const results=[];
 for(const suffix of ['','&forceRefresh=true&useCache=false','&forceRefresh=true']){
  const result=await request('category=smart-phones&budget=15000&limit=5'+suffix);const data=result.body.data;
  assert.deepEqual(data.products.map(p=>p.id),ids);
  data.products.forEach((p,i)=>{for(const key of Object.keys(baseline.products[i]))assert.deepEqual(p[key],baseline.products[i][key],'Preserve '+key);assert.equal(p.skip_live_price_check,true);assert.equal(p.live_price_status,'not_checked');});
  assert.equal(data.livePriceCandidatesChecked,0);assert.equal(data.priceVerificationStatus,'catalog_not_live');assert.equal(calls,0);assert.equal(workerCalls,0);assert.equal(writes,0);results.push(result);
 }
 fs.writeFileSync(path.join(pkg,'staged-api.json'),JSON.stringify(results,null,2));
 console.log('STAGING_TARGET',JSON.stringify({products:results[0].body.data.products.map(p=>({id:p.id,price:p.price_inr,url:p.product_url})),latencies:results.map(r=>r.ms),livePriceCalls:calls,workerCalls,writes}));
 for(const query of ['category=smart-phones&budget=12000','category=smart-phones&budget=20000','category=smart-phones&budget=15000.50','category=smart-phones&budget=15000&brand=Samsung','category=washing-machines&budget=15000','category=smart-tvs&budget=15000']){const before=calls;const r=await request(query);assert.ok(calls>before,'Normal verification retained '+query);assert.notEqual(r.body.data.livePriceVerificationSkipped,true);console.log('STAGING_REGRESSION',JSON.stringify({query,verificationCalls:calls-before,count:r.body.data.count,ms:r.ms}));}
 assert.equal(writes,0);assert.equal(workerCalls,0);
 await new Promise(resolve=>server.close(resolve));await mongoose.disconnect();console.log('STAGING_PASS');
})().catch(error=>{console.error(error.stack);process.exit(1);});
