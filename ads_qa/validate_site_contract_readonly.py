#!/usr/bin/env python3
"""Read-only HTTP smoke tests of live TrustFolio Top-5 and result-page routes.

Reads the production API origin from the existing website source. No writes,
no token use, no DB access, no production code modifications. Never prints
secrets, private data or raw response bodies.
"""
import json
import re
from pathlib import Path
from urllib.parse import urlencode, urlsplit, quote
from urllib.request import urlopen, Request

ROOT=Path.home()/"apps"/"trustfolio"
SOURCE=ROOT/"trustfolio-main/src/services/api.service.ts"

def request_json(url):
    with urlopen(Request(url,headers={"User-Agent":"TrustFolioAdsContractQA/1.0","Accept":"application/json"}),timeout=16) as response:
        if response.status != 200:
            raise ValueError("website backend did not return HTTP 200")
        if response.headers.get("Content-Type","").lower().find("json")<0:
            raise ValueError("website backend did not return JSON")
        data=response.read(450000)
        if len(data)>=450000:
            raise ValueError("unexpected large API response")
        return json.loads(data)

result={"mode":"read_only_public_website","checks":[]}
try:
    text=SOURCE.read_text("utf-8")
    found=re.search(r"const\s+PRODUCTION_API_BASE\s*=\s*['\x22](https://[^'\x22]+)['\x22]",text)
    if not found:raise ValueError("Website production API constant could not be resolved")
    base=found.group(1).rstrip("/")
    parts=urlsplit(base)
    if parts.scheme!="https" or not (parts.hostname=="trustfolio.in" or (parts.hostname or "").endswith(".trustfolio.in")):
        raise ValueError("API host outside TrustFolio HTTPS allowlist")
    result["api_host"]=parts.hostname
    url=base+"/api/products/top?"+urlencode({"category":"smartwatches","budget":2000,"limit":5})
    payload=request_json(url)
    data=payload.get("data")
    if payload.get("success") is not True or not isinstance(data,dict):
        raise ValueError("Top products endpoint did not return successful data object")
    products=data.get("products")
    if not isinstance(products,list):raise ValueError("Top products missing list")
    entries=[]
    for i,p in enumerate(products[:5],1):
        if not isinstance(p,dict):raise ValueError("Non-object product row")
        pid=str(p.get("id") or p.get("product_id") or "").strip()
        if not pid:raise ValueError("Missing product id")
        entries.append({"rank":p.get("rank",i),"id":pid,"price_inr":p.get("price_inr"),"brand":str(p.get("brand") or "")[:70]})
    result["checks"].append({"name":"top_products_smartwatches_2000","passed":True,"count":len(products),"items":entries,
        "match_type":data.get("matchType"),"fallback_applied":data.get("fallbackApplied")})
except Exception as exc:
    # Only print class/type; URLs/responses can contain sensitive details.
    result["checks"].append({"name":"top_products_smartwatches_2000","passed":False,"error_type":type(exc).__name__})
print("TRUSTFOLIO_SITE_LIVE_READONLY_BEGIN")
print(json.dumps(result,indent=2))
print("TRUSTFOLIO_SITE_LIVE_READONLY_END")
