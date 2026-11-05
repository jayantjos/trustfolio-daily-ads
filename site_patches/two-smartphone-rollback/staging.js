'use strict';
const fs=require('fs'),path=require('path'),Module=require('module'),assert=require('assert/strict'),http=require('http'),cp=require('child_process');
const root=process.cwd(),pkg=process.argv[2],mongoose=require('mongoose');
const runtime=JSON.parse(cp.execFileSync('pm2',['jlist'],{encoding:'utf8'})).find(p=>p.name==='trustfolio-backend').pm2_env;
const env={...require('dotenv').parse(fs.readFileSync('.env')),...runtime};
const uri=Object.values(env).find(v=>typeof v==='string'&&/^mongodb(\+srv)?:\/\//.test(v));
let writes=0,verificationCalls=0;
for(const proto of [mongoose.Collection.prototype,mongoose.mongo.Collection.prototype])for(const name of ['insertOne','insertMany','updateOne','updateMany','replaceOne','deleteOne','deleteMany','findOneAndUpdate','findOneAndReplace','findOneAndDelete','bulkWrite'])proto[name]=()=>{writes++;throw Error('Staging writes forbidden');};
function compile(relative,source){const filename=path.join(root,relative),m=new Module(filename);m.filename=filename;m.paths=Module._nodeModulePaths(path.dirname(filename));m._compile(source,filename);require.cache[filename]=m;return m.exports;}
const read=(folder,file)=>fs.readFileSync(path.join(pkg,folder,file),'utf8');
const ids=['69f9e9f56529299d30426ac8','69f9ea1f6529299d30426ae4','6a9e4a2e0933a0daedaddd80','6aa56d332bb194728fab44c3','6a2ed790ee20fca78fefdfde'];
const queries=[['smart-phones',15000],['smart-phones',12000],['smart-phones',20000],['smart-phones',15000,'Samsung'],['washing-machines',15000],['smart-tvs',15000],['smart-phones',15000.5]];
(async()=>{
 await mongoose.connect(uri,{dbName:'trustfolio',autoIndex:false,autoCreate:false});
 const beforeRanker=compile('services/ProductRecommendationService.js',read('before','ProductRecommendationService.js'));
 const beforeHelper=compile('services/LiveBudgetRecommendationService.js',read('before','LiveBudgetRecommendationService.js'));
 const before=[];for(const [category,budget,brand] of queries){before.push(await beforeHelper.getTopProductsForCategoryAndBudget(category,budget,{brand},{ranker:beforeRanker,prices:{async getLivePrices(list){return list.map(id=>({id,live:{status:'error',error:'isolated fixture'}}));}}}));}
 const ranker=compile('services/ProductRecommendationService.js',read('candidate','ProductRecommendationService.js'));
 const service=compile('services/LiveBudgetRecommendationService.js',read('candidate','LiveBudgetRecommendationService.js'));
 const dynamic=await ranker.getTopProductsForCategoryAndBudget('smart-phones',15000,{limit:5});
 const ignoredFlag=await ranker.getTopProductsForCategoryAndBudget('smart-phones',15000,{limit:5,exactSmartphoneBudget:true});assert.deepEqual(dynamic,ignoredFlag,'Former override flag has no effect');
 assert.ok(dynamic.products.length>0);assert.equal(new Set(dynamic.products.map(p=>p.id)).size,dynamic.products.length);
 const results=[];
 for(let i=0;i<queries.length;i++){
  const [category,budget,brand]=queries[i];let calls=0;
  const after=await service.getTopProductsForCategoryAndBudget(category,budget,{brand},{ranker,prices:{async getLivePrices(list){calls++;return list.map(id=>({id,live:{status:'error',error:'isolated fixture'}}));}}});
  assert.ok(calls>0);assert.equal(after.livePriceRefreshCompleted,true);assert.ok(after.products.every(p=>p.price_source==='website_catalog'&&p.live_price_status==='error'&&!p.skip_live_price_check));
  if(i>0)assert.deepEqual(after,before[i],'Unrelated query behavior unchanged '+queries[i]);
  results.push({query:queries[i],before:before[i].products.map(p=>({id:p.id,price:p.price_inr})),after:after.products.map(p=>({id:p.id,price:p.price_inr})),verificationCalls:calls,unchanged:i>0});
 }
 const priceFile=require.resolve(path.join(root,'services/LivePriceService'));
 require.cache[priceFile]={id:priceFile,filename:priceFile,loaded:true,exports:{async getLivePrices(list){verificationCalls++;return list.map(id=>({id,live:{status:'error',error:'controlled timeout'}}));}}};
 const controller=compile('controllers/ProductController.js',read('candidate','ProductController.js'));
 const server=http.createServer((req,res)=>{const query=Object.fromEntries(new URL(req.url,'http://localhost').searchParams);controller.getTopProducts({query},{status(n){res.statusCode=n;return this;},json(body){res.setHeader('Content-Type','application/json');res.end(JSON.stringify(body));return this;}});});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const httpResults=[];
 for(const [category,budget,brand] of queries){const query=new URLSearchParams({category,budget:String(budget),limit:'5',...(brand?{brand}:{})});const response=await fetch('http://127.0.0.1:'+server.address().port+'/api/products/top?'+query);const body=await response.json();assert.equal(response.status,200,JSON.stringify(body));assert.equal(body.data.livePriceRefreshCompleted,true);assert.ok(body.data.livePriceCandidatesChecked>0);assert.notEqual(body.data.livePriceVerificationSkipped,true);httpResults.push({query:String(query),body});}
 assert.ok(verificationCalls>0);assert.equal(writes,0);
 for(const source of ['ProductController.js','ProductRecommendationService.js','LiveBudgetRecommendationService.js','ProductsTable.tsx'].map(file=>read('candidate',file))){for(const token of [...ids,'exactSmartphoneBudget','skip_live_price_check','catalog_not_live','exact-15000-v1'])assert.ok(!source.includes(token),'Campaign token absent '+token);}
 fs.writeFileSync(path.join(pkg,'staging.json'),JSON.stringify({results,httpResults,dynamic,verificationCalls,writes},null,2));
 console.log('STAGING_DYNAMIC',JSON.stringify({products:dynamic.products.map(p=>({id:p.id,title:p.title,price:p.price_inr})),verificationCalls,writes,comparisons:results}));
 await new Promise(resolve=>server.close(resolve));await mongoose.disconnect();console.log('STAGING_ALL_PASS');
})().catch(e=>{console.error(e.stack);process.exit(1);});
