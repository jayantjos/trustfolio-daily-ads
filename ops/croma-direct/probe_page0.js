'use strict';
const {execFileSync}=require('node:child_process');
const samples=[
 {sku:'317985',q:'Croma 9 kg'},
 {sku:'303326',q:'noise'},
 {sku:'316655',q:'Lenovo LOQ'},
 {sku:'323239',q:'SONY BRAVIA'},
 {sku:'319977',q:'oppo Reno15 Pro'},
 {sku:'319062',q:'realme 15x 5G'}
];
for(const {sku,q} of samples){
 for(const page of [0,1]){
  const url=new URL('https://api.croma.com/searchservices/v1/search');
  for(const [k,v] of Object.entries({currentPage:String(page),query:q+' :relevance',fields:'FULL',channel:'WEB',channelCode:'400049',spellOpt:'DEFAULT'}))url.searchParams.set(k,v);
  try{
   const raw=execFileSync('curl',['-fsS','--max-time','7',url.toString()],{encoding:'utf8',timeout:8000,maxBuffer:5000000});
   const body=JSON.parse(raw);const products=Array.isArray(body.products)?body.products:[];
   const hit=products.find(row=>['code','skuId','productCode','id'].some(key=>row[key]!=null&&String(row[key])===sku));
   console.log('PAGE0_CROMA_PROBE='+JSON.stringify({sku,q,page,returned:products.length,current:body.pagination?.currentPage,total:body.pagination?.totalResults,hit:Boolean(hit),buyPrice:hit?.price?.value??null,sampleIds:products.slice(0,3).map(x=>x.code)}));
  }catch(e){console.log('PAGE0_CROMA_ERROR='+JSON.stringify({sku,q,page,error:String(e.message).slice(0,80)}));}
 }
}
console.log('READ_ONLY=YES');