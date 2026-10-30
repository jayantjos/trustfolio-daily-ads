'use strict';
const {createRequire}=require('node:module');const appRequire=createRequire(process.cwd()+'/package.json');
appRequire('dotenv').config();
(async()=>{
 const key=process.env.PRICE_WORKER_KEY;
 const oldUrl=process.env.PRICE_WORKER_URL||'';
 console.log('BACKEND_OLD_WORKER_URL_SET='+Boolean(oldUrl));
 console.log('BACKEND_OLD_WORKER_KEY_SET='+Boolean(key));
 if(!key){console.log('URL_ONLY_KEY_COMPATIBILITY=NOT_TESTABLE_NO_OLD_KEY_IN_SHELL');return;}
 const start=Date.now();
 try{
  const res=await fetch('https://trustfolio-live-price-worker.jayantjoshi-joshi.workers.dev/api/check',{
   method:'POST',headers:{'content-type':'application/json','x-api-key':key},
   body:JSON.stringify({items:['B0FNCLVRW5'],useCache:false}),
   signal:AbortSignal.timeout(12000)
  });
  console.log('NEW_WORKER_AUTH_WITH_EXISTING_BACKEND_KEY_HTTP='+res.status);
  if(res.status===401){console.log('URL_ONLY_CUTOVER_AUTH=FAIL_KEY_MISMATCH');return;}
  if(!res.ok){console.log('URL_ONLY_CUTOVER_AUTH=HTTP_OTHER');return;}
  const body=await res.json();const row=(body.results||[])[0]||{};
  const selected=row.asin?row.amazon:row.flipkart;
  console.log('NEW_WORKER_LEGACY_RESPONSE_ASIN_CORRECT='+Boolean(row.asin==='B0FNCLVRW5'));
  console.log('NEW_WORKER_LEGACY_RESPONSE_SELECT='+JSON.stringify({status:selected?.status,priceNum:selected?.priceNum,error:selected?.error||null}));
  console.log('URL_ONLY_CUTOVER_AUTH=PASS');
  console.log('WORKER_CALL_ELAPSED_MS='+String(Date.now()-start));
 }catch(e){console.log('NEW_WORKER_AUTH_TEST_ERROR='+String(e?.name||'network_error'))}
 console.log('BACKEND_AND_MONGODB_WRITES=NONE');
})().catch(e=>console.log('TEST_ERROR='+String(e.name||'error')));
