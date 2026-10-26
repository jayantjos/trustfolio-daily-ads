#!/usr/bin/env bash
set -euo pipefail
root="$HOME/apps/trustfolio"
front="$root/trustfolio-main"
back="$root/node-backend"
echo '==SITE_DEPLOY_CONTEXT=='
cd "$front"
node -p 'JSON.stringify(require("./package.json").scripts)'
echo '==UI_PRICE_CONTEXT=='
sed -n '299,370p' src/components/ProductsTable.tsx
echo '==TS_CONFIG=='
node -p 'JSON.stringify({name:require("./package.json").name,version:require("./package.json").version})'
echo '==BACKEND_ADAPTER=='
sed -n '1,160p' "$back/services/CromaLivePriceDirect.js"
echo '==MONGO_CROMA_SAMPLE=='
cd "$back"
node <<'JS'
require('dotenv').config();
const mongoose=require('mongoose'),connectDB=require('./config/mongo');
(async()=>{
 await connectDB();
 const rows=await mongoose.connection.collection('my_products').aggregate([
  {$match:{platform:'croma','platform_product_id':{$exists:true,$nin:[null,'']}}},
  {$match:{$or:[{'live.status':{$exists:false}},{'live.status':'no_price'}]}},
  {$sample:{size:8}},
  {$project:{platform_product_id:1,title:1,brand:1,category:1,product_url:1,price_inr:1}}
 ],{maxTimeMS:10000}).toArray();
 rows.forEach(p=>console.log('CROMA_CANDIDATE='+JSON.stringify({
 id:String(p._id),sku:p.platform_product_id,title:String(p.title||'').slice(0,140),
 brand:p.brand||null,category:p.category||null,price_inr:p.price_inr||null,
 url_sku:(String(p.product_url||'').match(/\/p\/(\d+)/)||[])[1]||null
 })));
})().catch(e=>{console.log('DIAG_ERROR='+e.message);process.exitCode=1}).finally(()=>mongoose.disconnect())
JS
