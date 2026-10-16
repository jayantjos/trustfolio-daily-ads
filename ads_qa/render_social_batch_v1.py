"""VPS-only TrustFolio 6-category x 3-format Instagram campaign batch.

Inputs: read-only public website's Top-5 API. Outputs only beneath
~/new_scraper/ads/ads_qa/batch-runs and ~/public_media/trustfolio-auto.
Does not modify ~/apps/trustfolio, scraper, or any social account.

A failed website query, unavailable brand or visual QA causes a SKIP,
never invented products / forced brand filters or automatic publication.
"""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from collections import Counter
import argparse, json, shutil, sys, traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from site_top5_ads_v1 import build_site_ads_payload
from automation.auto_campaign_v1 import campaign_id, package_assets

IST=ZoneInfo("Asia/Kolkata")
PLAN={
    "smartphones":{"slugs":["smart-phones"],"budgets":[15000,20000,25000],"brands":["Samsung","Redmi","realme","Motorola","Vivo"]},
    "televisions":{"slugs":["smart-tvs"],"budgets":[25000,30000,40000],"brands":["Samsung","LG","Mi","TCL","Sony"]},
    "laptops":{"slugs":["laptop","laptops"],"budgets":[55000,65000,75000],"brands":["HP","Lenovo","Dell","ASUS","Acer"]},
    "smartwatches":{"slugs":["smartwatches"],"budgets":[2000,3000,4000],"brands":["Noise","boAt","Fastrack","Fire-Boltt","Timex"]},
    "washing_machines":{"slugs":["washing-machines","washing-machine"],"budgets":[20000,25000,30000],"brands":["LG","Samsung","Whirlpool","IFB","Bosch"]},
    "earbuds":{"slugs":["headphones-earbuds"],"budgets":[3000,4000,5000],"brands":["boAt","Noise","JBL","Realme","OPPO"]},
}
MODES=("budget","brand_budget","comparison")


def website_candidate(slugs,budgets,*,reader=build_site_ads_payload):
    failures=[]
    for slug in slugs:
        for budget in budgets:
            try:
                source=reader(slug,budget,"")
                ad=source["ads"][0]
                if len(ad["products"])!=5:
                    raise ValueError("Incomplete website Top-5")
                return slug,budget,ad
            except Exception as exc:
                failures.append((slug,budget,type(exc).__name__))
    raise ValueError("No verified Top-5 within category budget tiers: "+str(failures))


def verified_brand(slug,budgets,base_ad,preferred,*,reader=build_site_ads_payload):
    # Prioritize names that actually appear in the site's current live Top-5.
    site_brands=[p.get("brand") or "" for p in base_ad["products"]]
    count=Counter(x.strip() for x in site_brands if str(x).strip())
    candidates=[x for x,_ in count.most_common()]+list(preferred)
    seen=set()
    for brand in candidates:
        brand=str(brand).strip()
        if not brand or brand.casefold() in seen:
            continue
        seen.add(brand.casefold())
        for budget in budgets:
            try:
                ad=reader(slug,budget,brand)["ads"][0]
                products=ad["products"]
                if len(products)!=5 or any(str(p.get("brand") or "").casefold()!=brand.casefold() for p in products):
                    raise ValueError("Website brand rank includes another brand")
                return brand,budget
            except Exception:
                continue
    raise ValueError("No brand has five verified live website products in configured budgets")


def run_batch(output_root,*,day,reader=build_site_ads_payload,renderer=None,packager=package_assets,public_dir=None):
    if renderer is None:
        from ads_qa.render_site_ranked_qa_v1 import run as renderer
    root=Path(output_root)
    root.mkdir(parents=True,exist_ok=True)
    result={"batch_date_ist":day,"account":"trustfolio3","source":"live_trustfolio_website_api",
            "publication_status":"not_scheduled","entries":[],"categories":list(PLAN)}
    for key,spec in PLAN.items():
        try:
            slug,budget,base_ad=website_candidate(spec["slugs"],spec["budgets"],reader=reader)
        except Exception as exc:
            for mode in MODES:
                result["entries"].append({"category_key":key,"mode":mode,"status":"skipped",
                                          "reason":type(exc).__name__})
            print("CATEGORY_SKIPPED="+key+";"+type(exc).__name__,flush=True)
            continue
        brand_data=None
        try:
            brand_data=verified_brand(slug,spec["budgets"],base_ad,spec["brands"],reader=reader)
        except Exception:
            pass
        for mode in MODES:
            if mode=="brand_budget" and brand_data is None:
                result["entries"].append({"category_key":key,"category":slug,
                                          "mode":mode,"status":"skipped",
                                          "reason":"NoFiveVerifiedSameBrandProducts"})
                print("AD_SKIPPED="+key+":"+mode+":NoFiveVerifiedSameBrandProducts",flush=True)
                continue
            selected_budget=brand_data[1] if mode=="brand_budget" else budget
            brand=brand_data[0] if mode=="brand_budget" else ""
            key_id=campaign_id(day+"-batch18",mode,slug,selected_budget,brand)
            folder=root/key/mode
            folder.mkdir(parents=True,exist_ok=True)
            plan={"status":"eligible","mode":mode,"date_ist":day,
                  "category":slug,"budget":selected_budget,"brand":brand,
                  "campaign_id":key_id,"account":"trustfolio3","auto_publish":False}
            try:
                # Regenerate directly from the live website on the ads VPS,
                # with EXACT rank positions and separately validated brand.
                renderer(slug,selected_budget,brand,folder,mode=mode)
                report=json.loads((folder/"website-top5-render-qa.json").read_text("utf8"))
                if report.get("campaign_mode")!=mode:
                    raise ValueError("Rendered campaign mode differs")
                plan["source_product_ids_by_rank"]=report["source_product_ids_by_rank"]
                (folder/"plan.json").write_text(json.dumps(plan,ensure_ascii=False,indent=2)+"\n")
                image,meta=packager(plan,report,folder/"trustfolio-live-website-top5-1024x1536.png",folder/"post")
                if meta["ranked_product_ids"]!=report["visual_product_ids_by_rank"]:
                    raise ValueError("Visual ad and post identity differ")
                # Stage the already verified JPEG; GitHub runner still must
                # GET and SHA256 verify it before any Metricool scheduling.
                public=Path(public_dir) if public_dir is not None else Path.home()/"public_media"/"trustfolio-auto"
                public.mkdir(parents=True,exist_ok=True)
                dest=public/image.name
                shutil.copy2(image,dest)
                dest.chmod(0o644)
                url="https://media.trustfolio.in/trustfolio-auto/"+image.name
                result["entries"].append({
                    "category_key":key,"category":slug,"mode":mode,
                    "brand":brand,"budget_inr":selected_budget,
                    "status":"qa_passed","campaign_id":key_id,
                    "website_source_ids":meta["ranked_product_ids"],
                    "landing_url":meta["landing_url"],"caption":meta["caption"],
                    "media_url":url,"local_jpg":"%s/%s/post/%s"%(key,mode,image.name),
                    "public_basename":image.name,
                    "ai_provenance":"original_reference_unverified",
                    "scheduling":"manual_metricool_connector_only",
                })
                print("AD_QA_PASSED="+key+":"+mode+";"+key_id,flush=True)
            except Exception as exc:
                result["entries"].append({
                    "category_key":key,"category":slug,"mode":mode,"status":"skipped",
                    "reason":type(exc).__name__,
                })
                print("AD_RENDER_SKIPPED="+key+":"+mode+";"+type(exc).__name__,flush=True)
        (root/"batch_index.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    count=sum(x["status"]=="qa_passed" for x in result["entries"])
    print("BATCH_READY="+str(count),flush=True)
    print("BATCH_SKIPPED="+str(len(result["entries"])-count),flush=True)
    print("LIVE_WEBSITE_APPS_MODIFIED=NO",flush=True)
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",required=True)
    ap.add_argument("--day",default=datetime.now(IST).date().isoformat())
    args=ap.parse_args()
    run_batch(args.output,day=args.day)


if __name__=="__main__":
    main()
