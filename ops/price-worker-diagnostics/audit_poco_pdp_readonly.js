'use strict';
require(process.cwd()+'/node_modules/dotenv').config();
const mongoose=require(process.cwd()+'/node_modules/mongoose');
const connectDB=require(process.cwd()+'/config/mongo');
const cp=require('node:child_process');
(async()=>{
 await connectDB();
 const col=mongoose.connection.collection('my_products');
 const sku='MOBHH2KYWG8UBBAF';
 const row=await col.findOne({platform:'flipkart',platform_product_id:sku},
 {projection:{_id:1,platform_product_id:1,title:1,price_inr:1,live:1,original_product_url:1}});
 if(!row)throw Error('SKU_NOT_FOUND_OR_DELETED');
 console.log('CURRENT_SKU='+sku);
 console.log('CURRENT_DB='+JSON.stringify({
  exists:true,id:String(row._id),price:row.price_inr,
  live_status:row.live?.status,live_checked_at:row.live?.checked_at,
  unavailable_checks:row.live?.unavailable_checks,availability_signal:row.live?.availability_signal,
  live_error:row.live?.error,http_status:row.live?.http_status
 }));
 const u=String(row.original_product_url||'');
 if(!/^https:\/\/www\.flipkart\.com\/.+\/p\/itm/.test(u)){
   console.log('CURL_SKIPPED_INVALID_PRODUCT_URL');return;
 }
 const page=await new Promise((resolve,reject)=>{
  cp.execFile('curl',['-sSL','--max-time','10','--connect-timeout','4','-w','\nHTTP_FINAL_STATUS=%{http_code}','-A','Mozilla/5.0','--url',u+'?pid='+sku],
   {encoding:'utf8',timeout:12000,maxBuffer:1500000},(e,out)=>{if(e)return reject(e);resolve(out)});
 });
 const html=page.replace(/\nHTTP_FINAL_STATUS=\d{3}$/,'');
 console.log('FLIPKART_VPS_CURL='+JSON.stringify({
   http:page.match(/HTTP_FINAL_STATUS=(\d{3})$/)?.[1]||'unknown',
   bytes:Buffer.byteLength(html),
   rupee_49999:/49,999|49999/.test(html),
   rupee_52999:/52,999|52999/.test(html),
   contains_exact_pid:html.includes(sku),
   access_denied:/access denied|captcha|unusual traffic|bot detected/i.test(html),
   title:/<title[^>]*>(.{0,150})<\/title>/i.exec(html)?.[1]||null
 }));
 console.log('MONGODB_WRITES=0');
})().catch(e=>{console.error('PDP_AUDIT_ERROR='+e.message);process.exitCode=1}).finally(()=>mongoose.disconnect());
