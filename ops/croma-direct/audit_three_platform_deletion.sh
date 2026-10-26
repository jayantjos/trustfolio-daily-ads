#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/apps/trustfolio/node-backend"
echo '===LIVE_PRICE_SERVICE_SOURCE_START==='
sed -n '1,260p' services/LivePriceService.js
echo '===LIVE_PRICE_SERVICE_SOURCE_END==='
echo '===CROMA_ADAPTER_SOURCE_START==='
sed -n '1,220p' services/CromaLivePriceDirect.js
echo '===CROMA_ADAPTER_SOURCE_END==='
echo '===MONGODB_STATUS_COUNTS_READ_ONLY==='
node <<'JS'
require('dotenv').config();
const mongoose=require('mongoose');
const connectDB=require('./config/mongo');
(async()=>{
 await connectDB();
 const col=mongoose.connection.collection('my_products');
 const a=await col.aggregate([
 {$match:{platform:{$in:['amazon','flipkart','croma']}}},
 {$group:{_id:{platform:'$platform',status:{$ifNull:['$live.status','never_checked']}},count:{$sum:1}}},
 {$sort:{'_id.platform':1,count:-1} }
 ],{maxTimeMS:15000}).toArray();
 a.forEach(row=>console.log('STATUS_COUNTS='+JSON.stringify(row)));
 const deleted=mongoose.connection.collection('my_products_deleted');
 console.log('DELETE_ARCHIVE_ESTIMATED_DOCS='+await deleted.estimatedDocumentCount());
})().catch(e=>{console.error('MONGO_AUDIT_FAILED='+e.message);process.exitCode=1}).finally(()=>mongoose.disconnect())
JS
