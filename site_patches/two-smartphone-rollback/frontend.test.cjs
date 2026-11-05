'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const ts=require(process.argv[2]+'/node_modules/typescript'),source=fs.readFileSync(process.argv[3]+'/candidate/ProductsTable.tsx','utf8');
const code=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
let calls=[],effects=[],hook=0,liveState={};
const React={createElement:(type,props,...children)=>({type:typeof type==='string'?type:'component',props:props||{},children}),useState(initial){hook++;return [hook===3?liveState:initial,()=>{}];},useEffect(fn){effects.push(fn);}};
const m={exports:{}};vm.runInNewContext(code,{module:m,exports:m.exports,React,AbortController,require(name){if(name==='react')return React;if(name==='next/image')return {default:'image'};if(name==='@/services/api.service')return {productService:{getLivePrices(ids){calls.push(ids);return Promise.resolve({success:true,data:[]});}}};throw Error(name);}});
for(const status of ['ok','error','timeout']){
 calls=[];effects=[];hook=0;liveState={a:{live:{status,price_inr:14000}}};
 const tree=m.exports.default({products:[{id:'a',title:'Dynamic candidate',rank:1,price_inr:13999,platform:'amazon',average_rating:'4',specifications:{},product_url:'https://retailer.test'}],maxPrice:15000});effects.forEach(fn=>fn());
 assert.equal(JSON.stringify(calls),JSON.stringify([['a']]));
 const text=JSON.stringify(tree);assert.equal(text.includes('"Live"'),status==='ok','Only verified response renders Live');
}
console.log('FRONTEND_NORMAL_POST_AND_BADGE_TEST_PASS');
