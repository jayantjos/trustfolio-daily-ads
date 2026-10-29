import {execFile} from 'node:child_process';
import {extractLiveStorePrice} from './WorkerPriceExtractionRules.mjs';
const url='https://www.flipkart.com/poco-x8-pro-max-blue-512-gb/p/itmfc8cc712fe4a5?pid=MOBHH2KYWG8UBBAF';
function curl(){return new Promise((resolve,reject)=>{
 execFile('curl',['-sSL','--max-time','13','--connect-timeout','5',
  '-w','\nHTTP_CODE=%{http_code}','-A','Mozilla/5.0','--url',url],
  {timeout:15000,maxBuffer:1600000,encoding:'utf8'},(err,output)=>{
    if(err)return reject(err);resolve(output)
  });
});}
try{
 const response=await curl();
 const code=Number((response.match(/HTTP_CODE=(\d{3})$/)||[])[1]);
 const html=response.replace(/\nHTTP_CODE=\d{3}$/,'');
 const parse=extractLiveStorePrice({platform:'flipkart',html,
   id:'MOBHH2KYWG8UBBAF',title:'POCO X8 Pro Max (Blue, 512 GB)'});
 const count=(s)=>[...html.matchAll(s)].length;
 console.log('REAL_PDP_RESPONSE='+JSON.stringify({
   http_code:code,bytes:Buffer.byteLength(html),
   has_pid:html.includes('MOBHH2KYWG8UBBAF'),
   offers_blocks:count(/"offers"\s*:/g),
   ppd_blocks:count(/"ppd"\s*:/g),
   fsp_tokens:count(/"fsp"\s*:/g),
   jsonld_scripts:count(/application\/ld\+json/gi),
   direct_49999:/49,999|49999/.test(html),
   direct_52999:/52,999|52999/.test(html),
   extracted:parse
 }));
 console.log('REAL_HTML_NO_MONGO_WRITES=YES');
}catch(e){console.log('REAL_PDP_TEST_ERROR='+e.message);process.exitCode=1;}
