'use strict';
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert/strict');
const out=process.argv[2];fs.mkdirSync(out,{recursive:true});
const ids=['69f9e9f56529299d30426ac8','69f9ea1f6529299d30426ae4','6a9e4a2e0933a0daedaddd80','6aa56d332bb194728fab44c3','6a2ed790ee20fca78fefdfde'];
(async()=>{
 const browser=await chromium.launch();const evidence=[];
 try{
  for(const [name,width,height] of [['mobile',390,844],['mobile-fresh',390,844],['desktop',1365,900]]){
   const context=await browser.newContext({viewport:{width,height},deviceScaleFactor:1,isMobile:width<500,hasTouch:width<500});const page=await context.newPage();
   const calls=[],errors=[];page.on('request',r=>calls.push({url:r.url(),method:r.method()}));page.on('pageerror',e=>errors.push(e.message));
   await page.goto('https://trustfolio.in/category/smart-phones/products/?budget=15000',{waitUntil:'networkidle',timeout:45000});
   await page.getByRole('heading',{name:/Redmi A7 Pro/i}).filter({visible:true}).waitFor({timeout:20000});
   const response=await context.request.get('https://api.trustfolio.in/api/products/top?category=smart-phones&budget=15000&limit=5');assert.equal(response.status(),200);const data=(await response.json()).data;
   assert.deepEqual(data.products.map(p=>p.id),ids);assert.equal(data.priceVerificationStatus,'catalog_not_live');
   const headings=page.locator('h4:visible').filter({hasText:/REDMI A7 Pro|Samsung Galaxy F06|Lava Bold N2|realme 14x|Motorola g64/i});assert.equal(await headings.count(),5);
   const cards=[];
   for(let i=0;i<5;i++){
    const heading=headings.nth(i),p=data.products[i];assert.equal(await heading.innerText(),p.title);
    const card=await heading.evaluate(h=>{const c=h.closest('tr')||h.closest('div.flex.items-center');return {text:c.innerText,href:c.querySelector('a[target="_blank"]')?.href,img:c.querySelector('img')?.getAttribute('src')};});
    assert.ok(card.text.includes(Number(p.price_inr).toLocaleString('en-IN')));assert.ok(card.img);assert.ok(!/(^|\n)Live($|\n)|Checking live/i.test(card.text));
    const expected=p.platform.toLowerCase().includes('amazon')&&p.asin?'https://www.amazon.in/dp/'+p.asin+'?tag=trustfolio62804-21':p.product_url;
    assert.equal(card.href,expected);cards.push({id:p.id,title:p.title,price:p.price_inr,...card});
   }
   assert.equal(calls.filter(c=>/\/api\/live-prices(?:[?\/]|$)|workers\.dev/.test(c.url)).length,0,'No browser live-price requests');
   assert.equal(errors.length,0,JSON.stringify(errors));
   const layout=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));assert.ok(layout.scrollWidth<=layout.width+2,'No horizontal overflow');
   await page.screenshot({path:out+'/'+name+'.png',fullPage:true});evidence.push({name,layout,cards,requests:calls,errors,livePriceRequests:0});
   await context.close();
  }
  const regressions=[];
  for(const query of ['category=smart-phones&budget=12000','category=smart-phones&budget=20000','category=smart-phones&budget=15000&brand=Samsung','category=washing-machines&budget=15000','category=smart-tvs&budget=15000']){
   const context=await browser.newContext(),start=Date.now();const response=await context.request.get('https://api.trustfolio.in/api/products/top?'+query,{timeout:60000});assert.equal(response.status(),200);const data=(await response.json()).data;
   assert.notEqual(data.livePriceVerificationSkipped,true);assert.equal(data.livePriceRefreshCompleted,true);assert.ok(data.livePriceCandidatesChecked>0);regressions.push({query,ms:Date.now()-start,count:data.count,livePriceRefreshCompleted:data.livePriceRefreshCompleted,livePriceCandidatesChecked:data.livePriceCandidatesChecked});await context.close();
  }
  fs.writeFileSync(out+'/acceptance.json',JSON.stringify({evidence,regressions},null,2));console.log('MOBILE_AND_PRODUCTION_REGRESSIONS_PASS',JSON.stringify({sessions:evidence.map(e=>({name:e.name,ids:e.cards.map(c=>c.id),livePriceRequests:e.livePriceRequests})),regressions}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exit(1);});
