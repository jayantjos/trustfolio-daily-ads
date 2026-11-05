'use strict';
const {chromium}=require('playwright'),assert=require('assert/strict'),fs=require('fs');
const out=process.argv[2];fs.mkdirSync(out,{recursive:true});const base='https://api.trustfolio.in';
const fixed=['69f9e9f56529299d30426ac8','69f9ea1f6529299d30426ae4','6a9e4a2e0933a0daedaddd80','6aa56d332bb194728fab44c3','6a2ed790ee20fca78fefdfde'];
const pause=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const browser=await chromium.launch();try{
  const request=(await browser.newContext()).request;const readiness=[];let ready=false;
  for(let n=0;n<20;n++){
   try{const r=await request.get(base+'/api/products/top?category=smart-phones&budget=15000&limit=5',{timeout:15000});let body;try{body=await r.json();}catch{}readiness.push({n,status:r.status(),count:body?.data?.count,live:body?.data?.livePriceRefreshCompleted});
    if(r.status()===200&&body?.data?.livePriceRefreshCompleted===true&&body.data.livePriceCandidatesChecked>0){ready=true;fs.writeFileSync(out+'/production-api.json',JSON.stringify(body,null,2));break;}
   }catch(error){readiness.push({n,error:error.message});}
   await pause(1000);
  }
  assert.ok(ready,'Original dynamic API did not become ready');fs.writeFileSync(out+'/readiness.json',JSON.stringify(readiness,null,2));
  const first=JSON.parse(fs.readFileSync(out+'/production-api.json')).data;
  assert.ok(first.count>0&&first.count<=5);assert.notDeepEqual(first.products.map(p=>p.id),fixed,'Not forced campaign order');
  const regressions=[];
  for(const query of ['category=smart-phones&budget=12000','category=smart-phones&budget=20000','category=smart-phones&budget=15000&brand=Samsung','category=washing-machines&budget=15000','category=smart-tvs&budget=15000']){
   const start=Date.now(),r=await request.get(base+'/api/products/top?'+query,{timeout:60000});assert.equal(r.status(),200);const body=await r.json(),d=body.data;
   assert.equal(d.livePriceRefreshCompleted,true);assert.ok(d.livePriceCandidatesChecked>0);assert.notEqual(d.livePriceVerificationSkipped,true);assert.ok(d.products.every(p=>p.price_inr>0&&p.price_inr<=Number(new URLSearchParams(query).get('budget'))));
   regressions.push({query,ms:Date.now()-start,body});
  }
  const sessions=[];
  for(const [name,width,height] of [['mobile',390,844],['mobile-fresh',390,844],['desktop',1365,900]]){
   const context=await browser.newContext({viewport:{width,height},isMobile:width<500,hasTouch:width<500}),page=await context.newPage();const calls=[],responses=[],errors=[];
   page.on('request',r=>{if(r.url().includes('/api/'))calls.push({url:r.url(),method:r.method(),body:r.postData()});});page.on('response',r=>{if(r.url().includes('/api/products/top')||r.url().includes('/api/live-prices'))responses.push(r);});page.on('pageerror',e=>errors.push(e.message));
   await page.goto('https://trustfolio.in/category/smart-phones/products/?budget=15000',{waitUntil:'networkidle',timeout:60000});
   await page.getByRole('heading',{name:'Recommended Products',exact:true}).waitFor({timeout:25000});
   const topResponse=responses.find(r=>r.url().includes('/api/products/top'));assert.ok(topResponse);assert.equal(topResponse.status(),200);const api=(await topResponse.json()).data;
   assert.equal(api.livePriceRefreshCompleted,true);assert.ok(api.livePriceCandidatesChecked>0);assert.notEqual(api.livePriceVerificationSkipped,true);assert.ok(api.products.every(p=>!p.skip_live_price_check));
   assert.equal(new Set(api.products.map(p=>p.id)).size,api.products.length);
   assert.ok(api.products.every(p=>p.price_inr>0&&p.price_inr<=15000&&(p.price_source!=='website_live_price_api'||p.live_price_status==='ok')));
   const liveResponse=responses.find(r=>r.url().includes('/api/live-prices'));assert.ok(liveResponse,'Frontend live-price request restored');assert.equal(liveResponse.status(),200);const live=(await liveResponse.json()).data;
   const table=page.locator('div.backdrop-blur-md').filter({has:page.getByRole('heading',{name:'Recommended Products',exact:true})}).last();
   const headings=table.locator('h4:visible'),cards=[];
   for(const p of api.products){const row=live.find(x=>x.id===p.id);assert.ok(row);if(row.deleted||(row.live?.status==='ok'&&row.live.price_inr>15000))continue;
    const h=headings.nth(cards.length);assert.equal(await h.innerText(),p.title);
    const card=await h.evaluate(h=>{const c=h.closest('tr')||h.closest('div.flex.items-center');return {text:c.innerText,href:c.querySelector('a[target="_blank"]')?.href,img:c.querySelector('img')?.getAttribute('src')};});
    const expected=p.platform.toLowerCase().includes('amazon')&&p.asin?'https://www.amazon.in/dp/'+p.asin+'?tag=trustfolio62804-21':p.product_url;assert.equal(card.href,expected);assert.ok(card.img);
    const price=['ok','out_of_stock'].includes(row.live?.status)&&row.live.price_inr?row.live.price_inr:p.price_inr;assert.ok(card.text.includes(Number(price).toLocaleString('en-IN')));const liveBadge=/(^|\n)Live($|\n)/.test(card.text);assert.equal(liveBadge,row.live?.status==='ok','No false Live badge');cards.push({id:p.id,price,liveStatus:row.live?.status,...card});
   }
   assert.equal(await headings.count(),cards.length);assert.ok(cards.length>0);assert.equal(errors.length,0,JSON.stringify(errors));assert.ok(calls.some(c=>c.method==='POST'&&c.url.includes('/api/live-prices')));
   const layout=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));assert.ok(layout.scrollWidth<=width+2);await page.screenshot({path:out+'/'+name+'.png',fullPage:true});sessions.push({name,cards,api,live,calls,errors,layout});await context.close();
  }
  fs.writeFileSync(out+'/acceptance.json',JSON.stringify({first,regressions,sessions},null,2));
  console.log('PRODUCTION_ROLLBACK_ACCEPTANCE_PASS',JSON.stringify({first:first.products.map(p=>({id:p.id,title:p.title,price:p.price_inr,source:p.price_source,status:p.live_price_status})),regressions:regressions.map(r=>({query:r.query,count:r.body.data.count,checked:r.body.data.livePriceCandidatesChecked,ms:r.ms})),sessions:sessions.map(s=>({name:s.name,ids:s.cards.map(c=>c.id),livePosts:s.calls.filter(c=>c.method==='POST'&&c.url.includes('/api/live-prices')).length}))}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exit(1);});
