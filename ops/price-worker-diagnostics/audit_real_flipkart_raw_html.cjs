'use strict';
// READ-ONLY two SKU HTTP/price-evidence probe; no credentials, no DB writes.
const {createRequire}=require('node:module');
const appRequire=createRequire(process.cwd()+'/package.json');
const mongoose=appRequire('mongoose');
appRequire('dotenv').config();
const mongoUri=['MONGODB_URI','MONGO_URI','MONGO_URL','MONGODB_URL','DB_URI','DATABASE_URL'].map(k=>process.env[k]).find(Boolean);
(async()=>{
 if(!mongoUri)throw Error('mongo_uri_not_configured');
 await mongoose.connect(mongoUri,{serverSelectionTimeoutMS:8000});
 const c=mongoose.connection.client.db('trustfolio').collection('my_products');
 const skus=['MOBHQFDZKKM7EEFZ','MOBH2AHZH779MGYF'];
 const docs=await c.find({platform:'flipkart',platform_product_id:{$in:skus}}).toArray();
 const workerItem=appRequire('./services/LivePriceService').workerItem;
 for(const d of docs){
   const item=workerItem(d);
   console.log('TEST_SKU='+JSON.stringify({pid:d.platform_product_id,
     title:String(d.title||'').slice(0,100),canonical_product_url:typeof item==='string'?item:null}));
   if(typeof item!=='string'||!item.startsWith('https://www.flipkart.com/'))continue;
   try {
     const response=await fetch(item,{headers:{
       accept:'text/html,application/xhtml+xml','accept-language':'en-IN,en;q=0.9',
       'user-agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
     },signal:AbortSignal.timeout(14500)});
     const html=(await response.text()).slice(0,1300000);
     const title=(/<title[^>]*>([^<]{0,200})<\/title>/i.exec(html)||[])[1]||'';
     const matches=[...html.matchAll(/(?:"(?:fsp|price)"\s*:\s*"?(?:₹)?\s*([\d,]{3,})|₹\s*[\d,]{3,})/gi)].length;
     const info={pid:d.platform_product_id,http_status:response.status,
       bytes:Buffer.byteLength(html),title:title.slice(0,155),
       pid_in_html:html.toUpperCase().includes(d.platform_product_id.toUpperCase()),
       jsonld_count:(html.match(/application\/ld\+json/gi)||[]).length,
       fsp_count:(html.match(/"fsp"\s*:/g)||[]).length,
       primary_price_element_count:(html.match(/\bNx9bqj\b/g)||[]).length,
       has_e002:/E002|something went wrong.{0,80}please try again later/i.test(html),
       visible_rupee_count:(html.match(/₹\s*[\d,]{3,}/g)||[]).length,
       mixed_price_evidence_count:matches};
     console.log('LIVE_FLIPKART_HTTP_EVIDENCE='+JSON.stringify(info));
   }catch(e){console.log('LIVE_FLIPKART_HTTP_PROBE_ERROR='+JSON.stringify({pid:d.platform_product_id,error:e?.name||'request_failed'}))}
 }
 console.log('HTTP_PROBE_READ_ONLY=YES');
})().catch(e=>{console.log('HTTP_PROBE_SETUP_ERROR='+String(e?.message||e).slice(0,140));process.exitCode=1}).finally(()=>mongoose.disconnect());
