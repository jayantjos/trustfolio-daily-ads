/**
 * TrustFolio Worker-ready HTML price extractor.
 * Ported from trustfolio-scraper/app/price_maintenance.py and legacy_price/scripts/price_update_worker.py.
 * Pure JS (Cloudflare Workers compatible): no Scrape.do, npm, process, DOM, or Node dependencies.
 *
 * IMPORTANT: Only run on HTML actually fetched for this exact product URL/ASIN/PID.
 * Do NOT infer a sale price from related/advertised products, MRP, cashback or EMI.
 */
const numeric = (value) => {
  if (value && typeof value === 'object') {
    return numeric(value.value ?? value.amount ?? value.price ?? value.raw);
  }
  if (value == null) return null;
  const str=String(value).trim().replace(/,/g,'').replace(/^₹\s*/,'');
  if (!/^\d{3,8}(?:\.\d{1,2})?$/.test(str)) return null;
  const n=Number(str);
  return Number.isFinite(n) && n >= 100 && n <= 10000000 ? n : null;
};
const norm=(s)=>String(s||'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
const result=(status,priceNum=null,source=null,availability=null,error=null)=>({
  status,priceNum,
  price:priceNum==null?null:'₹'+Number(priceNum).toLocaleString('en-IN'),
  inStock:availability==='in_stock'?true:availability==='out_of_stock'?false:null,
  availability,source,error
});
const COLORS=['black','blue','white','green','red','silver','gold','grey','gray','purple','violet','pink','orange','yellow','brown'];
function variantCompatible(expectedName,actualName) {
  const a=norm(expectedName), b=norm(actualName);
  const colorA=COLORS.find(c=>new RegExp('\\b'+c+'\\b').test(a));
  const colorB=COLORS.find(c=>new RegExp('\\b'+c+'\\b').test(b));
  if(colorA && colorB && colorA!==colorB)return false;
  const capacityA=/\b(64|128|256|512|1024) gb\b/.exec(a);
  const capacityB=/\b(64|128|256|512|1024) gb\b/.exec(b);
  if(capacityA && capacityB && capacityA[1]!==capacityB[1])return false;
  return true;
}
function productIdentityOK(html,expected) {
  const htmlTitle=(/<title[^>]*>([^<]{1,250})<\/title>/i.exec(html)||[])[1]||'';
  if (!htmlTitle || /captcha|access denied|something went wrong|robot check/i.test(htmlTitle)) return false;
  const expectedTitle=norm(expected?.title);
  if(expected?.title&&!variantCompatible(expected.title,htmlTitle))return false;
  if (!expectedTitle) return true;
  const words=expectedTitle.split(' ').filter(w=>w.length>2&&
      !['smartphone','mobile','online','best','price','ram','storage'].includes(w));
  const title=norm(htmlTitle);
  // Require model identity; one product detail page may display many unrelated ad items.
  return words.slice(0,2).some(w=>title.includes(w)) &&
      words.slice(0,4).filter(w=>title.includes(w)).length>=Math.min(2,words.slice(0,4).length);
}
function flattenProducts(obj,out) {
  if (!obj || typeof obj!=='object') return;
  if (Array.isArray(obj)) {for(const x of obj) flattenProducts(x,out);return;}
  const type=obj['@type'];
  if (Array.isArray(type)?type.some(t=>String(t).toLowerCase()==='product'):
      String(type||'').toLowerCase()==='product')out.push(obj);
  if(obj['@graph'])flattenProducts(obj['@graph'],out);
}
function priceFromJSONLD(html,expected) {
  const pattern=/<script\b[^>]*type\s*=\s*["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
  let match;
  while((match=pattern.exec(html))){
    let json;try{json=JSON.parse(match[1]);}catch(_){continue;}
    const products=[];flattenProducts(json,products);
    for(const p of products){
      // Never use an unrelated recommendation's Offer.
      if(expected?.title){
        if(!variantCompatible(expected.title,p.name))continue;
        const pageName=norm(p.name);
        const expectedTokens=norm(expected.title).split(' ').filter(w=>w.length>2);
        if(expectedTokens.length && expectedTokens.slice(0,4).filter(w=>pageName.includes(w)).length<2)continue;
      }
      const id=String(expected?.id||'').trim();
      const listedId=String(p.sku||p.productID||'');
      if(id && listedId && listedId!==id)continue;
      const offers=Array.isArray(p.offers)?p.offers:[p.offers];
      for(const offer of offers){
        if(!offer || typeof offer!=='object')continue;
        const amount=numeric(offer.price);
        if(amount==null)continue;
        const av=String(offer.availability||'').toLowerCase();
        if (/outofstock|soldout|discontinued/.test(av))return result('out_of_stock',null,'jsonld_offers', 'out_of_stock');
        return result('ok',amount,'jsonld_offers',/instock/.test(av)?'in_stock':null);
      }
    }
  }
  return null;
}
function parseFlipkart(html,expected={}) {
  if(typeof html!=='string'||html.length<800) return result('error',null,null,null,'empty_html');
  if(!productIdentityOK(html,expected)) return result('error',null,null,null,'page_identity_unverified');
  const jsonLd=priceFromJSONLD(html,expected);
  if(jsonLd)return jsonLd;
  // Old Scrape.do scraper preferred Flipkart PDP's fsp (final selling price)
  // over finalPrice and mrp. Only inspect a bounded PDP block.
  const ppd=/"ppd"\s*:\s*\{([\s\S]{0,1800}?)\}/gi; let m;
  while((m=ppd.exec(html))){
    const block=m[1];
    const fsp=/"fsp"\s*:\s*"?(\d{3,8})"?/.exec(block);
    const n=fsp?numeric(fsp[1]):null;
    if(n==null)continue;
    const near=html.slice(Math.max(0,m.index-350),Math.min(html.length,m.index+2500));
    if(/"NOTIFY_ME"\s*:\s*true/i.test(near))continue;
    return result('ok',n,'flipkart_ppd_fsp');
  }
  // Structured primary-product metadata is safer than scanning all rupee
  // amounts, which can include ads, MRP, similar products, exchange and EMI.
  const meta=/<meta\b[^>]*itemprop\s*=\s*["']price["'][^>]*content\s*=\s*["']([\d,.]+)["'][^>]*>/i.exec(html)
      || /<meta\b[^>]*content\s*=\s*["']([\d,.]+)["'][^>]*itemprop\s*=\s*["']price["'][^>]*>/i.exec(html);
  const metaPrice=numeric(meta?.[1]);
  if(metaPrice!=null)return result('ok',metaPrice,'product_meta_price');
  // An old scraper could parse "Buy at ₹X", but this is often CONDITIONAL
  // bank cashback. Treat it as diagnostic only, not the payable base price.
  if(/buy\s+at\s*₹\s*[\d,]+/i.test(html))
    return result('error',null,'buy_at_offer_only',null,'conditional_offer_not_base_price');
  // HTTP 200 on a valid PDP NEVER means 'not_listed' or 'not_available'.
  return result('error',null,null,null,'product_page_price_not_exposed');
}
function parseAmazon(html,expected={}) {
  if(typeof html!=='string'||html.length<800)return result('error',null,null,null,'empty_html');
  if(!productIdentityOK(html,expected))return result('error',null,null,null,'page_identity_unverified');
  const jsonLd=priceFromJSONLD(html,expected);
  if(jsonLd)return jsonLd;
  // Amazon buy-box / price-to-pay: exclude crossed-out MRP / list price.
  for(const marker of ['id="corePriceDisplay_desktop_feature_div"','id="corePrice_feature_div"',
    'id="priceToPay"','id="priceblock_dealprice"','id="priceblock_ourprice"']){
    const pos=html.indexOf(marker);
    if(pos<0)continue;
    const block=html.slice(pos,Math.min(pos+3500,html.length));
    const off=/<span[^>]*class=["'][^"']*\ba-offscreen\b[^"']*["'][^>]*>\s*(?:₹|Rs\.?)\s*([\d,]+(?:\.\d{1,2})?)\s*<\/span>/i.exec(block);
    const n=numeric(off?.[1]);
    if(n!=null)return result('ok',n,'amazon_buybox');
  }
  // Previous Amazon Scrape.do plugin used top-level price, not list_price.
  return result('error',null,null,null,'amazon_buybox_price_not_exposed');
}
export function extractLiveStorePrice({platform,html,id,title}) {
  const expected={id,title};
  if(String(platform).toLowerCase()==='flipkart')return parseFlipkart(html,expected);
  if(String(platform).toLowerCase()==='amazon')return parseAmazon(html,expected);
  return result('error',null,null,null,'unsupported_platform');
}
