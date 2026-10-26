#!/usr/bin/env bash
set -euo pipefail
root="$HOME/apps/trustfolio"
backend="$root/node-backend"
cd "$backend"
echo '=== PRODUCTION BACKEND ==='
node --check services/LivePriceService.js && echo 'BACKEND_SERVICE_SYNTAX=PASS'
node --check services/CromaLivePriceDirect.js && echo 'CROMA_ADAPTER_SYNTAX=PASS'
node <<'JS'
require('dotenv').config();
const mongoose=require('mongoose');
const connectDB=require('./config/mongo');
(async()=>{
 await connectDB();
 const p=await mongoose.connection.collection('my_products').findOne(
  {platform:'croma',platform_product_id:{$in:['317463',317463]}},
  {projection:{_id:1,platform:1,platform_product_id:1,title:1,price_inr:1,live:1}}
 );
 if (!p)throw Error('REFERENCE_CROMA_DOC_MISSING');
 console.log('CROMA_REFERENCE_DOCUMENT='+JSON.stringify({
   id:String(p._id),sku:String(p.platform_product_id),
   price_inr:p.price_inr,
   live_status:p.live?.status??null,live_checked_at:p.live?.checked_at??null,
   live_in_stock:p.live?.in_stock??null,
   live_price_inr:p.live?.price_inr??null
 }));
 const c=await mongoose.connection.collection('my_products').aggregate([
  {$match:{platform:'croma'}},
  {$group:{_id:{$ifNull:['$live.status','never_checked']},count:{$sum:1}}},
  {$sort:{count:-1}},{$limit:9}
 ],{maxTimeMS:8000}).toArray();
 console.log('CROMA_STATUS_COUNTS='+JSON.stringify(c));
})().catch(e=>{console.error('AUDIT_MONGO_ERROR='+e.message);process.exitCode=1}).finally(()=>mongoose.disconnect());
JS
echo '=== CONTROLLER AND ROUTE ==='
sed -n '1,60p' controllers/LivePriceController.js
grep -n -E 'live-prices|getLivePrices' routes/index.js | head -12 || true
echo '=== APP DIRECTORIES ==='
find "$root" -maxdepth 2 -mindepth 1 -type d ! -path '*/node_modules*' ! -path '*/.git*' | head -65
echo '=== FRONTEND SOURCE FILE MATCHES ==='
find "$root" -type d \( -name node_modules -o -name .git -o -name .next -o -name dist -o -name build -o -name coverage \) -prune -o -type f \( -name '*.jsx' -o -name '*.tsx' -o -name '*.js' -o -name '*.ts' \) \
  -size -250k -print 2>/dev/null | grep -v '/services/CromaLivePriceDirect.js' | grep -v '/node-backend/' | while IFS= read -r file; do
  hits=$(grep -nEi 'live.price|liveprice|liveStatus|isLivePrice|live.status|live-prices|live price|LivePriceBadge|priceStatus|live badge|pincodePrice' "$file" | head -15 || true)
  if [[ -n "$hits" ]]; then
     echo "MATCH_FILE=$file"
     printf '%s\n' "$hits" | cut -c 1-230
  fi
done | head -155
echo '=== BACKEND LIVE-PRICE ENDPOINT TEST ==='
node <<'JS'
require('dotenv').config();
const mongoose=require('mongoose');
const connectDB=require('./config/mongo');
(async()=>{
 await connectDB();
 const doc=await mongoose.connection.collection('my_products').findOne(
  {platform:'croma',platform_product_id:{$in:['317463',317463]}},{projection:{_id:1}}
 );
 if(!doc)throw Error('REFERENCE_PRODUCT_NOT_FOUND');
 const r=await fetch('https://api.trustfolio.in/api/live-prices',{
  method:'POST',headers:{'content-type':'application/json'},
  body:JSON.stringify({productIds:[String(doc._id)]}),
  signal:AbortSignal.timeout(10000)
 });
 console.log('PUBLIC_PRICE_HTTP='+r.status);
 const body=await r.text();
 try {
   const json=JSON.parse(body);
   const row=Array.isArray(json)?json[0]:Array.isArray(json.results)?json.results[0]:
     Array.isArray(json.data)?json.data[0]:null;
   console.log('PUBLIC_PRICE_RESPONSE_KEYS='+JSON.stringify(Object.keys(json).slice(0,14)));
   console.log('PUBLIC_PRICE_ROW='+JSON.stringify(row).slice(0,850));
   if(!row)console.log('PUBLIC_PRICE_BODY_SUMMARY='+JSON.stringify(json).slice(0,850));
 }catch(e){console.log('PUBLIC_PRICE_RESPONSE_NOT_JSON='+body.slice(0,180))}
})().catch(e=>{console.error('PUBLIC_API_QA_ERROR='+e.message);process.exitCode=1}).finally(()=>mongoose.disconnect());
JS
