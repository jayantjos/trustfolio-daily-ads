import assert from 'node:assert/strict';
import {extractLiveStorePrice as run} from './WorkerPriceExtractionRules.mjs';
const title='POCO X8 Pro Max (Blue, 512 GB) (12 GB RAM)';
const f={platform:'flipkart',title,id:'MOBHH2KYWG8UBBAF'};
const header='<html><head><title>'+title+' Online at Best Price On Flipkart.com</title></head>';
const footer='</html>';
const filler='<div>Product features and specifications</div>'.repeat(75);
const ld=(o)=>'<script type="application/ld+json">'+JSON.stringify(o)+'</script>';
const cases=[
 {name:'Flipkart schema.org Product Offer',html:header+ld({'@type':'Product',name:title,sku:f.id,offers:{price:'49999',availability:'https://schema.org/InStock'}})+filler+footer,price:49999,source:'jsonld_offers'},
 {name:'Flipkart fsp takes precedence over finalPrice and MRP',html:header+'<script type="application/json">{"ppd":{"fsp":49999,"finalPrice":52999,"mrp":61999}}</script>'+filler+footer,price:49999,source:'flipkart_ppd_fsp'},
 {name:'Flipkart bank offer cannot become base selling price',html:header+'<p>Buy at ₹47,499 apply offers</p><p>MRP ₹61,999</p>'+filler+footer,price:null,source:'buy_at_offer_only'},
 {name:'Flipkart unrelated ad has price but PDP does not',html:header+'<div>Ad: Samsung Galaxy Fold ₹214,999</div>'+filler+footer,price:null},
 {name:'Flipkart hydrated shell no price does not mean unavailable',html:header+'<h1>'+title+'</h1>'+filler+footer,price:null,status:'error'},
 {name:'Flipkart unrelated JSON-LD must not be used',html:header+ld({'@type':'Product',name:'Samsung Galaxy Fold 512GB',sku:'OTHER',offers:{price:'214999'}})+filler+footer,price:null},
 {name:'Flipkart explicit JSON-LD product OOS',html:header+ld({'@type':'Product',name:title,sku:f.id,offers:{price:'49999',availability:'https://schema.org/OutOfStock'}})+filler+footer,price:null,status:'out_of_stock'},
 {name:'Flipkart primary product meta price',html:header+'<meta itemprop="price" content="49999">'+filler+footer,price:49999,source:'product_meta_price'},
];
for(const c of cases){
 const got=run({...f,html:c.html});
 assert.equal(got.priceNum,c.price,c.name+': price');
 if(c.status)assert.equal(got.status,c.status,c.name+': status');
 if(c.source)assert.equal(got.source,c.source,c.name+': source');
 console.log('RULE_TEST_PASS='+c.name);
}
const amazonHtml='<html><head><title>Apple iPhone 16 (128 GB) - Amazon.in</title></head><body><div id="corePriceDisplay_desktop_feature_div"><span class="a-price"><span class="a-offscreen">₹69,900</span></span></div><p>MRP ₹79,900</p>'+filler+'</body></html>';
const a=run({platform:'amazon',title:'Apple iPhone 16 (128 GB)',id:'B0D1234567',html:amazonHtml});
assert.equal(a.priceNum,69900);
assert.equal(a.source,'amazon_buybox');
console.log('RULE_TEST_PASS=Amazon scoped buy-box not MRP');
console.log('RULE_TEST_SUITE=PASS');
