const test=require('node:test');
const assert=require('node:assert/strict');
const {selectLiveBudgetTop}=require('./live_budget_select');
const p=(id,platform,price)=>({id,platform,price_inr:price});
const r=(id,price,status='ok')=>({id,deleted:false,live:{status,price_inr:price}});
test('out-of-budget listing replaced by next ranked eligible product',()=>{
  const candidates=[p('1','amazon',34000),p('2','flipkart',34500),p('3','amazon',33000),
    p('4','croma',31000),p('5','flipkart',32000),p('6','flipkart',32500),p('7','amazon',32800)];
  const rows=[r('1',37250),r('2',34000),r('3',33000),r('4',31000,'unavailable'),r('5',32000),r('6',32500),r('7',32800)];
  const final=selectLiveBudgetTop(candidates,rows,35000);
  assert.equal(final.length,5);
  assert.equal(final.some(x=>x.id==='1'),false);
  assert.deepEqual(final.map(x=>x.rank),[1,2,3,4,5]);
  assert.ok(final.every(x=>x.price_inr<=35000));
  assert.deepEqual(final.map(x=>x.id),['2','3','4','5','7']);
});
test('deleted, out-of-stock, missing-row, and duplicate are safely rejected',()=>{
  const products=[p('1','amazon',1000),p('2','amazon',1000),p('2','amazon',1000),
    p('3','flipkart',1000),p('4','croma',1000),p('5','flipkart',1000)];
  const rows=[{...r('1',900),deleted:true},r('2',900,'out_of_stock'),r('3',950),r('4',null,'unsupported')];
  const final=selectLiveBudgetTop(products,rows,1000);
  assert.deepEqual(final.map(x=>x.id),['3','4']);
});
test('all returned prices remain within the budget hard maximum',()=>{
  for(const limit of [1,2,5]) {
    const products=Array.from({length:15},(_,i)=>p('id'+i,i%3===0?'amazon':i%3===1?'flipkart':'croma',6000));
    const rows=products.map((x,i)=>r(x.id, i%2===0?6001:5999));
    const final=selectLiveBudgetTop(products,rows,6000,limit);
    assert.ok(final.length<=limit);
    assert.ok(final.every(x=>x.price_inr<=6000));
  }
});
test('valid catalog price fallback is allowed when refresh is blocked',()=>{
  const final=selectLiveBudgetTop([p('c1','croma',4500)],[r('c1',10000,'blocked')],5000);
  assert.equal(final[0].price_inr,4500);
  assert.equal(final[0].price_source,'catalog_fallback');
});
