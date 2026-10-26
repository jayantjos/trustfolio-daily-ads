#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/apps/trustfolio/node-backend"
front="$HOME/apps/trustfolio/trustfolio-main"
echo '=== FRONTEND TYPE AND API ==='
sed -n '1,95p' "$front/src/types/product.ts"
sed -n '343,366p' "$front/src/services/api.service.ts"
echo '=== FRONTEND PRODUCT TABLE ==='
sed -n '290,420p' "$front/src/components/ProductsTable.tsx"
sed -n '420,540p' "$front/src/components/ProductsTable.tsx"
echo '=== BACKEND CORRECT /api/live-prices POST ==='
node <<'JS'
require('dotenv').config();
const mongoose=require('mongoose');
const connectDB=require('./config/mongo');
(async()=>{
 await connectDB();
 const doc=await mongoose.connection.collection('my_products').findOne(
  {platform:'croma',platform_product_id:{$in:['317463',317463]}},{projection:{_id:1,live:1}});
 if(!doc)throw Error('SKU_317463_NOT_FOUND');
 console.log('MONGO_REFERENCE_ID='+doc._id);
 console.log('MONGO_LIVE_BEFORE='+JSON.stringify({status:doc.live?.status,checked_at:doc.live?.checked_at}));
 const resp=await fetch('https://api.trustfolio.in/api/live-prices',{
  method:'POST',headers:{'content-type':'application/json'},
  body:JSON.stringify({ids:[String(doc._id)]}),
  signal:AbortSignal.timeout(12000)
 });
 console.log('HTTP_STATUS='+resp.status);
 const body=await resp.text();
 try {
   const j=JSON.parse(body);
   console.log('LIVE_API_SUCCESS='+j.success);
   console.log('LIVE_API_DATA_LENGTH='+(j.data?.length??'NOT_ARRAY'));
   const row=j.data?.[0]||null;
   console.log('LIVE_API_PRODUCT='+JSON.stringify(row));
 }catch(_){console.log('LIVE_API_PARSE_FAILED='+body.slice(0,100))}
})().catch(e=>{console.log('API_DIAGNOSTIC_ERROR='+e.message);process.exitCode=1}).finally(()=>mongoose.disconnect())
JS
