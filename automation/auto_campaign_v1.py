"""Deterministic, fail-closed TrustFolio social campaign planner and asset packer.

Reads public TrustFolio website Top-5 only. No scraper, app source, DB, or
website changes. Comparison means comparing five *different* top picks,
never a fabricated cross-retailer price saving for the same model.
"""
import argparse
import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlencode
from zoneinfo import ZoneInfo

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from site_top5_ads_v1 import build_site_ads_payload

IST = ZoneInfo("Asia/Kolkata")
MODES = ("budget", "brand_budget", "comparison")
REPO_HOST = "www.trustfolio.in"


def campaign_id(day, mode, category, budget, brand):
    value = "|".join((str(day), mode, category, str(budget), brand.casefold()))
    return "tfauto-" + hashlib.sha256(value.encode()).hexdigest()[:18]


def choose_campaign(mode, policy, *, day, overrides=None, fetcher=build_site_ads_payload):
    if mode not in MODES:
        raise ValueError("Unsupported campaign type")
    day = date.fromisoformat(str(day))
    overrides = overrides or {}
    if any(overrides.values()):
        category = str(overrides.get("category") or "").strip()
        budget = overrides.get("budget")
        brand = str(overrides.get("brand") or "").strip()
        if not category or not budget or (mode == "brand_budget" and not brand):
            raise ValueError("Manual campaign requires category/budget and brand for brand mode")
        candidates = [{"category": category, "budget": budget, "brand": brand}]
    else:
        candidates = list(policy["campaigns"][mode])
        if not candidates:
            raise ValueError("Empty campaign schedule")
        offset = day.toordinal() % len(candidates)
        candidates = candidates[offset:] + candidates[:offset]

    failures = []
    for candidate in candidates:
        category = str(candidate["category"]).strip()
        budget = int(candidate["budget"])
        brand = str(candidate.get("brand") or "").strip() if mode == "brand_budget" else ""
        try:
            payload = fetcher(category, budget, brand)
            ad = payload["ads"][0]
            products = ad["products"]
            if len(products) != 5 or ad.get("ranking_source") != "live_trustfolio_website_api":
                raise ValueError("Top-five website ranking missing")
            ids = [p.get("product_id") for p in products]
            if not all(ids) or len(set(ids)) != 5:
                raise ValueError("Website source product IDs invalid")
            result = {
                "status": "eligible", "mode": mode, "date_ist": day.isoformat(),
                "category": category, "budget": budget, "brand": brand,
                "campaign_id": campaign_id(day,mode,category,budget,brand),
                "source_product_ids_by_rank": ids,
                "source_observed_at": payload.get("generated_at"),
                "post_network": "instagram", "account": "trustfolio3",
                "auto_publish": False,  # only the Metricool gate can allow it
            }
            return result
        except (ValueError, KeyError, IndexError, TypeError, OSError) as error:
            failures.append({"category":category,"budget":budget,"brand":brand,
                             "reason":type(error).__name__})
    return {"status":"no_eligible_campaign","mode":mode,"date_ist":day.isoformat(),
            "attempts":failures,"auto_publish":False}


def check_report(plan, report):
    if plan.get("status") != "eligible":
        raise ValueError("Cannot render ineligible campaign")
    if report.get("source") != "live_trustfolio_website_api":
        raise ValueError("Only the live website API may determine ranking")
    if report.get("campaign_category") != plan["category"] or int(report.get("campaign_budget_inr") or 0) != plan["budget"]:
        raise ValueError("Rendered category or budget changed")
    if (report.get("campaign_brand") or "") != plan["brand"]:
        raise ValueError("Rendered brand changed")
    ids = report.get("source_product_ids_by_rank")
    if ids != report.get("visual_product_ids_by_rank") or len(ids or []) != 5:
        raise ValueError("Website and infographic rankings differ")
    if not all(ids) or len(set(ids)) != 5:
        raise ValueError("Duplicate or missing website product IDs")
    if report.get("visual_geometry_errors") or report.get("dimensions") != [1024,1536]:
        raise ValueError("Infographic geometry or size not approved")
    if report.get("renderer") != "master_template_renderer_html_v4":
        raise ValueError("Approved premium renderer not used")
    url = urlsplit(str(report.get("landing_url") or ""))
    if url.scheme != "https" or url.hostname not in ("trustfolio.in", REPO_HOST) or not url.path.endswith("/products"):
        raise ValueError("Landing URL is not the real TrustFolio results page")
    params = parse_qs(url.query)
    if params.get("budget") != [str(plan["budget"])] or params.get("brand",[""])[0] != plan["brand"]:
        raise ValueError("Campaign landing filters do not match the visual ad")
    if report.get("automatic_publication") is not False:
        raise ValueError("Rendering must not publish without approval gate")
    # Rankings can change between planning and rendering; the website-render
    # report is authoritative for the actual image. Always record its ID order.
    return ids


def caption_for(plan, landing_url):
    category = plan["category"].replace("-", " ").title()
    brand = plan["brand"]
    budget = format(plan["budget"],",")
    if plan["mode"] == "brand_budget":
        title = f"Best {brand} {category} Under ₹{budget}!"
        body = f"{brand} ke Top 5 picks dekho — prices aur features compare karo."
    elif plan["mode"] == "comparison":
        title = f"Compare Top 5 {category} Under ₹{budget}!"
        body = "5 alag products ko side-by-side compare karo. Same-product price savings ka claim nahi."
    else:
        title = f"Best {category} Under ₹{budget}!"
        body = "Top 5 ranked picks, latest listed prices aur shopping options dekho."
    tags = "#TrustFolio #SmartShopping #ProductComparison #BestDealsIndia"
    hub_filters = {"category":plan["category"],"budget":str(plan["budget"])}
    if brand: hub_filters["brand"] = brand
    hub = ("https://media.trustfolio.in/trustfolio-links/index.html?"
           + urlencode(hub_filters))
    # Instagram captions are not clickable. The brand's bio needs a one-time
    # profile Links update; do not claim it is active until verified.
    return (f"✨ {title}\n\n{body}\n\n"
            f"🔎 Filtered results: {landing_url}\n"
            f"🔗 Website + app quick links: {hub}\n"
            "📲 Android app: https://play.google.com/store/apps/details?id=com.trustfolio.app\n"
            "Instagram feed links tappable nahi hote. Link copy karo; "
            "bio link activate hone ke baad profile se direct open karo.\n\n"
            "Prices, availability aur ranking badal sakte hain; buy karne se pehle verify karo.\n\n"
            + tags)


def package_assets(plan, report, original_png, output_dir):
    from PIL import Image, ImageFilter, ImageOps
    ids = check_report(plan, report)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(original_png) as original:
        if original.size != (1024,1536):
            raise ValueError("Wrong original image dimensions")
        rgb = original.convert("RGB")
        # Instagram feed 4:5: letterbox original portrait without cropping
        # any product, logo, benefits pill or footer.
        background = ImageOps.fit(rgb, (1080,1350), Image.Resampling.LANCZOS)
        background = background.filter(ImageFilter.GaussianBlur(60))
        background = Image.blend(background, Image.new("RGB",(1080,1350),(224,235,250)),.52)
        foreground = ImageOps.contain(rgb,(1080,1350),Image.Resampling.LANCZOS)
        background.paste(foreground,((1080-foreground.width)//2,(1350-foreground.height)//2))
        jpg = output_dir / (plan["campaign_id"]+".jpg")
        background.save(jpg,"JPEG",quality=95,optimize=True,subsampling=0)
    with Image.open(jpg) as verify:
        if verify.size!=(1080,1350):
            raise ValueError("Invalid Instagram image")
    content = caption_for(plan, report["landing_url"])
    metadata = {
        "campaign_id":plan["campaign_id"],"mode":plan["mode"],
        "date_ist":plan["date_ist"],"category":plan["category"],
        "budget_inr":plan["budget"],"brand":plan["brand"],
        "network":"instagram","instagram_account":"trustfolio3",
        "ranked_product_ids":ids,"ranking_observed_at":report.get("source_observed_at"),
        "landing_url":report["landing_url"],"caption":content,
        "source_renderer":report["renderer"],"geometry_errors":[],
        "output_jpg":jpg.name,"size":[1080,1350],
        "status":"ready_for_publishing_gate","publication_status":"not_published",
    }
    (output_dir/"post.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    (output_dir/"caption.txt").write_text(content+"\n",encoding="utf8")
    return jpg, metadata


def main():
    parser=argparse.ArgumentParser()
    subs=parser.add_subparsers(dest="action",required=True)
    p=subs.add_parser("select")
    p.add_argument("--mode",choices=MODES,required=True)
    p.add_argument("--day",default=datetime.now(IST).date().isoformat())
    p.add_argument("--policy",default="automation/campaigns.json")
    p.add_argument("--category",default="")
    p.add_argument("--budget",default="")
    p.add_argument("--brand",default="")
    p.add_argument("--output",required=True)
    q=subs.add_parser("package")
    for arg in ("plan","report","image","output_dir"):
        q.add_argument("--"+arg.replace("_","-"),required=True)
    args=parser.parse_args()
    if args.action=="select":
        policy=json.loads(Path(args.policy).read_text("utf8"))
        overrides={"category":args.category,"budget":args.budget,"brand":args.brand}
        plan=choose_campaign(args.mode,policy,day=args.day,overrides=overrides)
        Path(args.output).write_text(json.dumps(plan,indent=2)+"\n",encoding="utf8")
        print("CAMPAIGN_STATUS="+plan["status"])
        if plan["status"]=="eligible":
            print("CAMPAIGN_ID="+plan["campaign_id"])
    else:
        plan=json.loads(Path(args.plan).read_text("utf8"))
        report=json.loads(Path(args.report).read_text("utf8"))
        jpg,manifest=package_assets(plan,report,args.image,args.output_dir)
        print("INSTAGRAM_ASSET_READY="+str(jpg))
        print("RANKED_PRODUCT_IDS="+",".join(manifest["ranked_product_ids"]))


if __name__=="__main__":
    main()
