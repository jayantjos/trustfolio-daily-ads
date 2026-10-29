'use strict';
// Exact-SKU Flipkart official Affiliate Product API adapter.
// The API requires authorized Flipkart credentials. This module never exposes them.
// Unconfigured / invalid / unavailable API: returns null; existing Worker remains fallback.

const ENDPOINT='https://affiliate-api.flipkart.net/affiliate/1.0/product.json';
const norm=s=>String(s||'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
const COLORS=['black','blue','white','green','red','silver','gold','grey','gray','purple','violet','pink','orange','yellow','brown'];
function sameVariant(expected,actual) {
  const a=norm(expected),b=norm(actual);
  const prefix=s=>s.split(' ').filter(x=>x.length>2&&!['storage','online','best','price','ram','mobile','smartphone'].includes(x));
  const tokens=prefix(a);
  if(tokens.length>=2 && tokens.slice(0,4).filter(x=>b.split(' ').includes(x)).length<2)return false;
  const color=name=>COLORS.find(c=>new RegExp('\\b'+c+'\\b').test(name));
  if(color(a)&&color(b)&&color(a)!==color(b))return false;
  const cap=name=>/\b(64|128|256|512|1024)\s*gb\b/.exec(name)?.[1];
  if(cap(a)&&cap(b)&&cap(a)!==cap(b))return false;
  return true;
}
function parseProduct(body,doc) {
  const p=body?.productBaseInfoV1 || body?.productBaseInfo?.productAttributes || null;
  if (!p || typeof p!=='object')return null;
  const pid=String(p.productId||'').trim().toUpperCase();
  const expected=String(doc.platform_product_id||'').trim().toUpperCase();
  if(pid!==expected || !sameVariant(doc.title,p.title))return null;
  // Strictly use actual merchant selling price, NEVER MRP or special/coupon price.
  const offer=p.flipkartSellingPrice || p.sellingPrice;
  if (offer?.currency && String(offer.currency).toUpperCase()!=='INR')return null;
  const price=Number(offer?.amount);
  if (!Number.isFinite(price)||price<100||price>10000000)return null;
  if (p.inStock===false){
    // Explicit stock status: still require marketplace confirmation logic, no price LIVE.
    return {status:'not_available',availability:'not_available',in_stock:false,
      source:'flipkart_affiliate_product',http_status:200};
  }
  return {status:'ok',priceNum:price,inStock:p.inStock===true?true:null,in_stock:p.inStock===true?true:null,
    availability:p.inStock===true?'in_stock':null,
    source:'flipkart_affiliate_product',http_status:200};
}
async function fetchFlipkartOfficial(doc,opts={}) {
  const id=String(doc?.platform_product_id||'').trim().toUpperCase();
  if(String(doc?.platform||'').toLowerCase()!=='flipkart'||!/^[A-Z0-9]{10,24}$/.test(id))return null;
  const env=opts.env||process.env;
  const affiliateId=String(env.FLIPKART_AFFILIATE_ID||'').trim();
  const affiliateToken=String(env.FLIPKART_AFFILIATE_TOKEN||'').trim();
  if(!affiliateId||!affiliateToken)return null;
  const impl=opts.fetch||globalThis.fetch;
  try{
    const res=await impl(ENDPOINT+'?id='+encodeURIComponent(id),{
      method:'GET',
      headers:{'Fk-Affiliate-Id':affiliateId,'Fk-Affiliate-Token':affiliateToken,accept:'application/json'},
      signal:AbortSignal.timeout(4500)
    });
    if(!res.ok)return null;
    const body=await res.json();
    return parseProduct(body,doc);
  }catch(_){return null;}
}
module.exports={fetchFlipkartOfficial,parseProduct,sameVariant};
