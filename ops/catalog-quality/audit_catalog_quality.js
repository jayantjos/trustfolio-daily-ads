'use strict';
// Read-only: catalog quality metrics. No product updates or deletions.
require('dotenv').config();
const mongoose=require('mongoose');
const connectDB=require('./config/mongo');
const colNames=['my_products','my_products_deleted'];
(async()=>{
 await connectDB();
 const col=mongoose.connection.collection(colNames[0]);
 const group=await col.aggregate([
   {$group:{_id:{$ifNull:['$platform','unknown']}, count:{$sum:1},
    missing_title:{$sum:{$cond:[{$or:[{$eq:['$title',null]},{$eq:['$title','']}]},1,0]}},
    missing_sku:{$sum:{$cond:[{$or:[{$eq:['$platform_product_id',null]},{$eq:['$platform_product_id','']}]},1,0]}},
    price_null:{$sum:{$cond:[{$and:[{$eq:['$price_inr',null]},{$eq:['$price',null]}]},1,0]}},
    live_ok:{$sum:{$cond:[{$eq:['$live.status','ok']},1,0]}},
    never_checked:{$sum:{$cond:[{$eq:['$live.status',null]},1,0]}},
    temp_error:{$sum:{$cond:[{$in:['$live.status',['blocked','error','store_error','no_price','skipped','timeout']]},1,0]}}
   }},
   {$sort:{count:-1}}
 ],{maxTimeMS:30000}).toArray();
 console.log('CATALOG_QUALITY_PLATFORM_COUNTS='+JSON.stringify(group));
 const exactDup=await col.aggregate([
   {$match:{platform:{$in:['amazon','flipkart','croma']},platform_product_id:{$nin:[null,'']}}},
   {$group:{_id:{platform:'$platform',sku:'$platform_product_id'},n:{$sum:1}}},
   {$match:{n:{$gt:1}}},
   {$group:{_id:'$_id.platform',groups:{$sum:1},excess_documents:{$sum:{$subtract:['$n',1]}},largest_group:{$max:'$n'}}}
 ],{maxTimeMS:30000,allowDiskUse:true}).toArray();
 console.log('CATALOG_DUPLICATE_SKU_GROUPS='+JSON.stringify(exactDup));
 const archive=await mongoose.connection.collection('my_products_deleted').estimatedDocumentCount();
 console.log('ARCHIVED_PRODUCT_COUNT='+archive);
 const suspect=await col.aggregate([
   {$match:{'live.status':{$in:['not_listed','not_found','out_of_stock','discontinued','sold_out']}}},
   {$group:{_id:{platform:'$platform',status:'$live.status'},n:{$sum:1}}},
   {$sort:{n:-1}}
 ],{maxTimeMS:10000}).toArray();
 console.log('CATALOG_OLD_UNAVAILABLE_STATUS='+JSON.stringify(suspect));
 console.log('DATABASE_WRITES=0');
})().catch(e=>{console.error('CATALOG_AUDIT_ERROR='+e.message);process.exitCode=1}).finally(()=>mongoose.disconnect());
