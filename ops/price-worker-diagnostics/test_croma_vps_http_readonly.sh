#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import subprocess,json,urllib.parse
q={'currentPage':'0','query':'Crompton Energion Hyperjet :relevance','fields':'FULL',
   'channel':'WEB','channelCode':'400049','spellOpt':'DEFAULT'}
url='https://api.croma.com/searchservices/v1/search?'+urllib.parse.urlencode(q)
try:
 p=subprocess.run(['curl','-sS','-L','--connect-timeout','3','--max-time','10',
   '-w','\n__CROMA_HTTP__%{http_code}','--url',url],
   capture_output=True,text=True,timeout=14)
 if '__CROMA_HTTP__' not in p.stdout:
  print('VPS_CROMA_DIRECT_RESULT=no_http', 'exitcode='+str(p.returncode));raise SystemExit(0)
 raw,code=p.stdout.rsplit('\n__CROMA_HTTP__',1)
 print('VPS_CROMA_DIRECT_HTTP='+code.strip())
 try:
  data=json.loads(raw)
  products=data.get('products') if isinstance(data,dict) else None
  if isinstance(products,list):
   hit=next((r for r in products if isinstance(r,dict) and any(str(r.get(k,''))=='300154'
    for k in ['code','skuId','productCode','id'])),None)
   print('VPS_CROMA_PRODUCTS_COUNT='+str(len(products)))
   print('VPS_CROMA_SKU_300154_MATCH='+str(hit is not None))
   if hit:
    n=hit.get('price')
    print('VPS_CROMA_PRICE_TYPE='+str((n or {}).get('priceType') if isinstance(n,dict) else None))
    print('VPS_CROMA_PRICE_VALUE='+str((n or {}).get('value') if isinstance(n,dict) else None))
 except Exception:print('VPS_CROMA_JSON_PARSE=FAIL')
except Exception as e:print('VPS_CROMA_TEST_ERROR='+type(e).__name__)
print('TEST_READ_ONLY=YES')
PY
