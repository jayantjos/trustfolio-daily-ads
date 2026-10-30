#!/usr/bin/env python3
"""QA-only: 300 real Mongo products, 200 fresh Cloudflare checks, 100 VPS Croma checks."""
import concurrent.futures,csv,io,json,pathlib,urllib.parse,urllib.request,urllib.error,zipfile
R=pathlib.Path("qa-reports");R.mkdir(exist_ok=True)
DATE="2026-10-30";BASE="https://trustfolio-live-price-worker.jayantjoshi-joshi.workers.dev"
def readlog(name):
    b=pathlib.Path(name).read_bytes()
    if zipfile.is_zipfile(io.BytesIO(b)):
        with zipfile.ZipFile(io.BytesIO(b)) as z:b=b"\n".join(z.read(n) for n in z.namelist() if not n.endswith("/"))
    return b.decode("utf8","replace")
def parse_marker(line,key):
    if key not in line:return None
    try:return json.loads(line.split(key,1)[1].strip())
    except (ValueError,IndexError):return None
source=readlog("qa-export.log")
meta=next((parse_marker(x,"TF_100_QA_METADATA=") for x in source.splitlines() if "TF_100_QA_METADATA=" in x and "console.log" not in x),None)
if not meta:raise SystemExit("EXPORT_NOT_AVAILABLE")
inventory=meta["platforms"]
if any(len(inventory.get(k,[]))!=100 for k in ("amazon","flipkart","croma")):raise SystemExit("SAMPLES_INCOMPLETE")
croma_log=readlog("qa-croma.log")
results=[parse_marker(x,"CROMA_100_RESULT=") for x in croma_log.splitlines() if "CROMA_100_RESULT=" in x and "console.log" not in x]
croma={str(x["sku"]):x for x in results if isinstance(x,dict)}
if len(croma)<95:raise SystemExit("CROMA_LOG_INCOMPLETE")
print("CROMA_REAL_RESULTS="+str(len(croma)),flush=True)
def worker_check(task):
    platform,index,p=task
    url=BASE+"/qa/check-100?"+urllib.parse.urlencode({"platform":platform,"index":index})
    rep=None;err="";http=None
    try:
        req=urllib.request.Request(url,headers={"accept":"application/json","user-agent":"TrustFolioQA/1.0"})
        with urllib.request.urlopen(req,timeout=25) as response:
            http=response.status;rep=json.loads(response.read().decode("utf8")).get("report")
        if not rep:err="report_missing"
    except urllib.error.HTTPError as e:http=e.code;err="qa_http_"+str(e.code)
    except Exception as e:err="qa_"+type(e).__name__
    return {"Platform":platform,"Category":p["category"],"Product":p["title"],"SKU":p["sku"],
     "Product Link":p["url"],"MongoDB Price":p["stored_price"],"Fresh Price":rep.get("priceINR") if rep else None,
     "Status":rep.get("status") if rep else "error","Error":(rep.get("error") or "") if rep else err,
     "Price Source":rep.get("source") if rep else "", "Identity Verified":rep.get("identityVerified") if rep else None,
     "HTTP":rep.get("httpStatus") if rep else http,
     "Checked At UTC":rep.get("checkedAt") if rep else "", "Manual Verification":"Pending",
     "Test Method":"Own Cloudflare Worker: no cache; no browser"}
tasks=[(k,i,p) for k in ("amazon","flipkart") for i,p in enumerate(inventory[k])]
print("LIVE_WORKER_CHECKS_START="+str(len(tasks)),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:rows=list(executor.map(worker_check,tasks))
print("LIVE_WORKER_CHECKS_COMPLETE="+str(len(rows)),flush=True)
for p in inventory["croma"]:
    x=croma.get(p["sku"],{})
    rows.append({"Platform":"croma","Category":p["category"],"Product":p["title"],"SKU":p["sku"],
      "Product Link":x.get("url") or p["url"],"MongoDB Price":p["stored_price"],
      "Fresh Price":x.get("live_price"),"Status":x.get("status") or "not_checked",
      "Error":x.get("error") or "","Price Source":"VPS Croma direct exact-SKU API",
      "Identity Verified":bool(x),"HTTP":None,"Checked At UTC":"2026-10-30",
      "Manual Verification":"Pending","Test Method":"VPS Croma direct API (Cloudflare 403)"})
assert len(rows)==300
stem=DATE+"-300-product-price-check"
with (R/(stem+".csv")).open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(R/(stem+".json")).write_text(json.dumps({"date":DATE,"count":300,"rows":rows},ensure_ascii=False,indent=2),encoding="utf8")
output=["# TrustFolio - 300 Product Live Price Audit - 30 October 2026","",
 "**Read-only test:** no MongoDB writes, deletions or production Worker migration.",
 "Amazon and Flipkart: own Cloudflare Worker. Croma: existing VPS direct API (Cloudflare test HTTP 403).",
 "Extracted prices are not independently checked against the marketplace yet: manually confirm exact variant and seller.",
 "","## Overall results","",
 "| Platform | Tested | Price extracted | Missing / error | Changed vs MongoDB |","|---|---:|---:|---:|---:|"]
for platform in ("amazon","flipkart","croma"):
    subset=[r for r in rows if r["Platform"]==platform]
    valid=[r for r in subset if r["Fresh Price"] is not None]
    changed=sum(r["Fresh Price"]!=r["MongoDB Price"] for r in valid)
    output.append(f"| {platform.title()} | {len(subset)} | {len(valid)} | {len(subset)-len(valid)} | {changed} |")
output+=["","N/A indicates unverified live price; the catalog price is historical and must not be labelled Live.",""]
for platform in ("amazon","flipkart","croma"):
    output.extend(["## "+platform.title()+" - 100 products","",
      "| # | Open product | SKU | MongoDB price | Fresh price | Status | Error | Manual verified |",
      "|---:|---|---|---:|---:|---|---|---|"])
    for ix,r in enumerate((r for r in rows if r["Platform"]==platform),1):
        title=r["Product"].replace("|","/").replace("[","(").replace("]",")").strip()[:78]
        fresh="₹"+format(int(r["Fresh Price"]),",") if r["Fresh Price"] is not None else "N/A"
        stored="₹"+format(int(r["MongoDB Price"]),",") if r["MongoDB Price"] is not None else "-"
        error=str(r["Error"] or "").replace("|","/")[:50]
        output.append(f"| {ix} | [{title}]({r['Product Link']}) | {r['SKU']} | {stored} | {fresh} | {r['Status']} | {error} | [ ] |")
    output.append("")
(R/(stem+".md")).write_text("\n".join(output),encoding="utf8")
from collections import Counter
for platform in ("amazon","flipkart","croma"):
    sub=[r for r in rows if r["Platform"]==platform]
    good=[r for r in sub if r["Fresh Price"] is not None]
    print("FINAL_100_SUMMARY="+json.dumps({"platform":platform,"tested":len(sub),"priced":len(good),
      "unverified":len(sub)-len(good),"changed":sum(r["Fresh Price"]!=r["MongoDB Price"] for r in good),
      "statuses":dict(Counter(r["Status"] for r in sub))}),flush=True)
print("REPORT_FILES="+",".join(str(v) for v in R.glob(stem+".*")),flush=True)
