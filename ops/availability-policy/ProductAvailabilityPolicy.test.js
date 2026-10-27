'use strict';
const assert=require('node:assert/strict');
const {classify,toAvailabilityState,isConfirmedUnavailable}=require('./ProductAvailabilityPolicy');
for (const label of ['out_of_stock','sold_out','sold out','discontinued',
  'This item is discontinued','item sold out','permanently_unavailable']) {
 const x={status:label};assert.equal(classify(x),'permanent',label);
 assert.equal(isConfirmedUnavailable({...x,unavailable_checks:1}),true,label);
}
for(const label of ['n/a','N/A','not available','unavailable','not_listed','not_found','404']) {
 const x={status:label};assert.equal(classify(x),'ambiguous',label);
 const a={...x,...toAvailabilityState(x)};
 assert.equal(isConfirmedUnavailable(a),false,label+' first check');
 const b={...x,...toAvailabilityState(x,a)};
 assert.equal(isConfirmedUnavailable(b),true,label+' confirmed second check');
}
for(const label of ['no_price','error','blocked','store_error','skipped','502','http_502','timeout','page_load_failed']) {
 const x={status:label,error:'worker http 502'};
 assert.equal(classify(x),'transient',label);
 assert.equal(isConfirmedUnavailable({...x,unavailable_checks:400}),false,label);
}
const ambiguous={status:'not_listed'};
const a={...ambiguous,...toAvailabilityState(ambiguous)};
const transient={status:'error',error:'HTTP 502'};
const b={...transient,...toAvailabilityState(transient,a)};
assert.equal(b.unavailable_checks,0);
const c={...ambiguous,...toAvailabilityState(ambiguous,b)};
assert.equal(c.unavailable_checks,1);
assert.equal(classify({status:'ok',availability:'item sold out'}),'permanent');
assert.equal(classify({status:'ok',availability:'not available'}),'ambiguous');
assert.equal(classify({status:'ok',availability:'available'}),'none');
assert.equal(classify({status:'ok',http_status:502,availability:'out of stock'}),'transient');
assert.equal(classify({status:'no_price',availability:null}),'transient');
assert.equal(classify({status:'no_price',availability:'this item is discontinued'}),'permanent');
assert.equal(classify({status:'no_price',availability:'N/A'}),'ambiguous');
console.log('AVAILABILITY_POLICY_TEST=PASS');
console.log('HTTP_502_MASS_DELETE_GUARD=PASS');
console.log('NA_TWO_FRESH_CHECKS=PASS');
