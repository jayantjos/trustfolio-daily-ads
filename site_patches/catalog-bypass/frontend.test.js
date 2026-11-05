'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const ts=require(process.argv[2]+'/node_modules/typescript');
const source=fs.readFileSync(process.argv[3]+'/ProductsTable.tsx','utf8');
const code=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
let calls=[],effects=[],hook=0;
const element=(type,props,...children)=>({type,props:props||{},children});
const React={createElement:element,useState(initial){hook++;return [hook===3?{a:{deleted:true,live:{status:'ok',price_inr:99999}}}:hook===4?true:initial,()=>{}];},useEffect(fn){effects.push(fn);}};
const m={exports:{}};
vm.runInNewContext(code,{module:m,exports:m.exports,React,AbortController,require(name){if(name==='react')return React;if(name==='next/image')return {default:'image'};if(name==='@/services/api.service')return {productService:{getLivePrices(ids){calls.push(ids);return Promise.resolve({success:true,data:[]});}}};throw Error(name);}});
function render(skip){calls=[];effects=[];hook=0;const tree=m.exports.default({products:[{id:'a',title:'Existing model',rank:1,price_inr:14489,platform:'amazon',average_rating:'4',skip_live_price_check:skip,product_url:'https://retailer.test',specifications:{}}],maxPrice:15000});effects.forEach(fn=>fn());return JSON.stringify(tree);}
const target=render(true);assert.equal(calls.length,0);assert.ok(target.includes('14,489'));assert.ok(!target.includes('99,999'));assert.ok(!target.includes('Checking live'));assert.ok(!target.includes('>Live<'));
render(false);assert.equal(JSON.stringify(calls),JSON.stringify([['a']]));console.log('FRONTEND_PASS: target no POST, stale live deletion/price ignored, normal requests still POST');
