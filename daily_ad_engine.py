import json, os, re
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

BASE = Path.home() / "new_scraper"
OUT = BASE / "ads" / "daily_ad_test.json"
CATEGORY = "smart-phones"
PLATFORMS = ("amazon","flipkart","croma")
MAX_BUDGET_ADS = 3
MAX_BRAND_ADS = 3
MAX_COMPARISON_ADS = 3
PRODUCTS_PER_AD = 5
BUDGET_TOL = 0.10
MIN_SAVING_PCT = 2.0
LIMIT = 5000

GENERIC = {
    "add","ai","android","bluetooth","computer","desktop","earbuds","good",
    "in ear","kids","mobile","phone","portable","smart","tablet","truly",
    "wireless","10","10 1","2025","7"
}

load_dotenv(BASE / ".env")
URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI") or os.getenv("MONGODB_URL")
DB = os.getenv("MONGODB_DB","trustfolio")
COL = os.getenv("PRODUCT_COLLECTION","my_products")
if not URI:
    raise RuntimeError("MongoDB URI not found in ~/new_scraper/.env")
client = MongoClient(URI, serverSelectionTimeoutMS=5000)
products = client[DB][COL]

def clean(v):
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9]+"," ",str(v or "").lower())).strip()

def price(p):
    try:
        return float(p.get("price_inr") or 0)
    except Exception:
        m=re.search(r"\d+(?:\.\d+)?",str(p.get("price","")).replace(",",""))
        return float(m.group()) if m else 0

def platform(p): return str(p.get("platform") or "").lower().strip()
def brand(p): return str(p.get("brand") or "").strip()
def title(p): return str(p.get("title") or "").strip()

def model_key(p):
    s=clean(title(p))
    s=re.sub(r"\b(?:smartphone|smart phone|mobile phone|mobile|phone)\b"," ",s)
    s=re.sub(r"\b\d+(?:\.\d+)?\s*(?:gb|tb|mah)\b"," ",s)
    for x in ("black","white","blue","green","red","grey","gray","silver","gold",
              "pink","purple","orange","yellow","titanium","navy","brown","violet"):
        s=re.sub(rf"\b{re.escape(x)}\b"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def valid(p):
    return (
        p.get("category")==CATEGORY and
        p.get("price_ready") is True and
        str(p.get("availability") or "").lower()=="available" and
        platform(p) in PLATFORMS and price(p)>0 and bool(title(p))
    )

def leading_brand(p):
    b,t=clean(brand(p)),clean(title(p))
    return bool(b and t and (t==b or t.startswith(b+" ")))

def safe_brand(b):
    b=clean(b)
    return bool(b and b not in GENERIC and not re.fullmatch(r"[\d\s.+-]+",b) and len(b)>=2)

def payload(p):
    return {
        "product_id":str(p.get("product_id") or p.get("id") or p.get("asin") or p.get("_id") or p.get("product_url") or ""),
        "title":title(p),
        "brand":brand(p),
        "price_inr":round(price(p),2),
        "rating":p.get("average_rating",p.get("rating")),
        "image_url":p.get("main_image") or p.get("image") or "",
        "product_url":p.get("product_url") or "",
        "platform":platform(p),
        "category":CATEGORY,
        "specifications":p.get("specifications") or {}
    }

docs=list(products.find({
    "category":CATEGORY,
    "price_ready":True,
    "availability":"available",
    "platform":{"$in":list(PLATFORMS)}
},{
    "product_id":1,"id":1,"asin":1,"_id":1,"title":1,"brand":1,"price":1,"price_inr":1,
    "average_rating":1,"rating":1,"main_image":1,"image":1,"product_url":1,"platform":1,
    "category":1,"specifications":1,"price_ready":1,"availability":1
}).limit(LIMIT))
docs=[p for p in docs if valid(p)]

def diverse(items, n=PRODUCTS_PER_AD):
    out=[]; used_models=set(); used_pf=set()
    for p in items:
        k=model_key(p); pf=platform(p)
        if not k or k in used_models or pf in used_pf: continue
        out.append(p); used_models.add(k); used_pf.add(pf)
        if len(out)>=n: return out
    for p in items:
        k=model_key(p)
        if not k or k in used_models: continue
        out.append(p); used_models.add(k)
        if len(out)>=n: break
    return out

platform_counts=Counter(platform(p) for p in docs)

# Budget targets from observed prices.
prices=sorted({int(price(p)) for p in docs if price(p)>0})
targets=[]
if prices:
    for i in range(min(MAX_BUDGET_ADS,len(prices))):
        idx=round(i*(len(prices)-1)/max(MAX_BUDGET_ADS-1,1))
        if prices[idx] not in targets: targets.append(prices[idx])

budget_ads=[]
for b in targets:
    cand=[p for p in docs if price(p)<=b*(1+BUDGET_TOL)]
    cand.sort(key=lambda p:(abs(price(p)-b),-float(p.get("average_rating") or p.get("rating") or 0)))
    sel=diverse(cand)
    pfs={platform(x) for x in sel}
    if len(sel)>=3 and set(PLATFORMS)<=pfs:
        budget_ads.append({
            "ad_type":"budget_recommendation",
            "category":CATEGORY,
            "headline":f"Best Smartphones Under ₹{b:,}",
            "budget_inr":b,
            "platforms":sorted(pfs),
            "products":[payload(x) for x in sel]
        })

# Safe brand groups.
bs=defaultdict(list)
for p in docs:
    b=clean(brand(p))
    if safe_brand(b) and leading_brand(p):
        bs[b].append(p)

brand_candidates=[]
for b,items in bs.items():
    pfs={platform(x) for x in items}
    if not set(PLATFORMS)<=pfs: continue
    if len(items)<3: continue
    brand_candidates.append((b,items))
brand_candidates.sort(key=lambda x:len(x[1]),reverse=True)

brand_ads=[]
for b,items in brand_candidates:
    items=sorted(items,key=price)
    target=price(items[len(items)//2])
    cand=[p for p in items if price(p)<=target*(1+BUDGET_TOL)]
    cand.sort(key=lambda p:(abs(price(p)-target),-float(p.get("average_rating") or p.get("rating") or 0)))
    sel=diverse(cand)
    pfs={platform(x) for x in sel}
    if len(sel)>=3 and set(PLATFORMS)<=pfs:
        disp=brand(sel[0]) or b
        brand_ads.append({
            "ad_type":"brand_recommendation",
            "category":CATEGORY,
            "brand":disp,
            "headline":f"Best {disp} Smartphones",
            "platforms":sorted(pfs),
            "products":[payload(x) for x in sel]
        })
        if len(brand_ads)>=MAX_BRAND_ADS: break

# Exact 3-platform comparison candidates.
groups=defaultdict(lambda:defaultdict(list))
for p in docs:
    b=clean(brand(p)); mk=model_key(p)
    if b and mk: groups[(b,mk)][platform(p)].append(p)

comp=[]
for (b,mk),by in groups.items():
    if not all(pf in by for pf in PLATFORMS): continue
    sel={pf:min(by[pf],key=price) for pf in PLATFORMS}
    ps={pf:price(sel[pf]) for pf in PLATFORMS}
    lo,hi=min(ps.values()),max(ps.values())
    if lo<=0 or hi<=0: continue
    save=hi-lo
    pct=(save/hi)*100
    if pct<MIN_SAVING_PCT: continue
    comp.append((pct,save,b,mk,sel,ps))
comp.sort(reverse=True,key=lambda x:(x[0],x[1]))
comparison_ads=[]
for pct,save,b,mk,sel,ps in comp[:MAX_COMPARISON_ADS]:
    comparison_ads.append({
        "ad_type":"price_comparison",
        "category":CATEGORY,
        "brand":brand(sel["amazon"]),
        "model":mk,
        "headline":f"Compare {brand(sel['amazon'])} {mk}",
        "platforms":list(PLATFORMS),
        "prices":ps,
        "best_platform":min(ps,key=ps.get),
        "best_price_inr":min(ps.values()),
        "saving_inr":round(save,2),
        "saving_percent":round(pct,2),
        "products":{pf:payload(sel[pf]) for pf in PLATFORMS}
    })

ads=budget_ads+brand_ads+comparison_ads
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps({
    "brand":{"name":"Trustfolio","website":"https://www.trustfolio.in","app":"Trustfolio"},
    "generated_at":datetime.now().isoformat(),
    "source":"Trustfolio MongoDB",
    "generated_from_live_mongodb":True,
    "trustfolio_backend_unchanged":True,
    "engine":"daily_ad_engine_test_v1",
    "category":CATEGORY,
    "platforms_required":list(PLATFORMS),
    "stats":{
        "eligible_products":len(docs),
        "platform_counts":dict(platform_counts),
        "budget_ads":len(budget_ads),
        "brand_ads":len(brand_ads),
        "comparison_ads":len(comparison_ads),
        "total_ads":len(ads)
    },
    "ads":ads
},ensure_ascii=False,indent=2),encoding="utf-8")

print("="*70)
print("TRUSTFOLIO DAILY AD ENGINE - SMARTPHONES TEST")
print("="*70)
print("Eligible products:",len(docs))
print("Platform counts  :",dict(platform_counts))
print("Budget ads       :",len(budget_ads))
print("Brand ads        :",len(brand_ads))
print("Comparison ads   :",len(comparison_ads))
print("TOTAL ADS        :",len(ads))
print("OUTPUT           :",OUT)
print("="*70)

client.close()
