'use strict';
const {execFileSync}=require('node:child_process');
const list=[
 {sku:'317985',qs:['Croma 9 kg top load','Croma 9 kg','Croma washing machine']},
 {sku:'303326',qs:['noise Three','Noise Bluetooth Headphones','noise']},
 {sku:'316655',qs:['Lenovo LOQ 15IRX9','Lenovo LOQ']},
 {sku:'323239',qs:['SONY BRAVIA 3 II','SONY BRAVIA']},
 {sku:'319977',qs:['oppo Reno15 Pro 5G','oppo Reno15 Pro']}
];
let calls=0;
for(const p of list){
 let found=false;
 for(const q of p.qs){
   if(found)break;
   for(let page=1;page<=2;page++){
     const url=new URL('https://api.croma.com/searchservices/v1/search');
     Object.entries({currentPage:String(page),query:q+' :relevance',fields:'FULL',channel:'WEB',channelCode:'400049',spellOpt:'DEFAULT'}).forEach(([k,v])=>url.searchParams.set(k,v));
     calls++;
     try{
       const raw=execFileSync('curl',['-fsS','--connect-timeout','3','--max-time','7',url.toString()],{encoding:'utf8',timeout:8000,maxBuffer:5000000});
       const body=JSON.parse(raw),products=Array.isArray(body.products)?body.products:[];
       const hit=products.find(x=>[x.code,x.skuId,x.productCode,x.id].some(x=>x!=null&&String(x)===p.sku));
       console.log('CROMA_PROBE='+JSON.stringify({sku:p.sku,q,page,results:products.length,total:body.pagination?.totalResults??null,hit:Boolean(hit),price:hit?.price?.value??null,sampleIds:products.slice(0,3).map(x=>x.code)}));
       if(hit){found=true;break;}
       if(products.length===0 || Number(body.pagination?.totalPages||0)<=page)break;
     }catch(e){console.log('CROMA_PROBE_ERROR='+JSON.stringify({sku:p.sku,q,page,error:String(e.message).slice(0,70)}));break;}
   }
 }
 console.log('CROMA_SKU_PROBE_RESULT='+JSON.stringify({sku:p.sku,found}));
}
console.log('TOTAL_PROBE_CALLS='+calls);
console.log('MONGODB_WRITES=0');