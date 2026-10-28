"""Deterministic, fail-closed TrustFolio social campaign planner and asset packer.

Reads public TrustFolio website Top-5 only. No scraper, app source, DB, or
website changes. Comparison means comparing five *different* top picks,
never a fabricated cross-retailer price saving for the same model.
"""
import argparse
import hashlib
import json
import re
from calendar import monthrange
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


def _same_parity_days_before(day):
    """Count preceding dates with the same odd/even day-of-month since 2000.

    Count by Gregorian month, not ordinal//2: October 31 and November 1
    are both odd dates. This keeps the odd and even category queues separate
    across month and year boundaries without silently skipping a category.
    """
    if day.year < 2000:
        raise ValueError("Campaign calendar starts in year 2000")
    odd = day.day % 2 == 1
    count = (day.day - 1) // 2
    for year in range(2000, day.year):
        for month in range(1, 13):
            days = monthrange(year, month)[1]
            count += (days + 1) // 2 if odd else days // 2
    for month in range(1, day.month):
        days = monthrange(day.year, month)[1]
        count += (days + 1) // 2 if odd else days // 2
    return count


def rotation_candidates(mode, policy, day, *, slot=0):
    """Odd/even calendar-date category cohorts and rotating budget tiers.

    Odd dates select one of ten categories at indices 0,2,...,18; even dates
    select indices 1,3,...,19. Each ad format has its own offset and two
    separately scheduled slots with non-overlapping primary categories.
    A category's primary budget advances every ten same-parity dates (one
    complete cohort cycle); even dates begin a different tier from odd dates.
    All category retries stay in their parity cohort. Missing real Top-5
    website data must be skipped, never fabricated.
    """
    rotation = policy.get("rotation") or {}
    categories = rotation.get("categories") or []
    if not categories:
        return None  # backwards-compatible legacy campaigns
    if len(categories) != 20 or len({x["key"] for x in categories}) != 20:
        raise ValueError("Daily rotation requires 20 unique canonical categories")
    if type(slot) is not int or slot not in (0, 1):
        raise ValueError("Daily rotation slot must be 0 or 1")
    offsets = rotation.get("mode_category_offsets") or {}
    cohort_size = len(categories) // 2
    same_parity_slot = _same_parity_days_before(day)
    # Odd days use even indices (0,2,...); even days use odd indices (1,3,...).
    parity_offset = 0 if day.day % 2 else 1
    index = 2 * ((same_parity_slot + int(offsets.get(mode, 0)) + 2 * slot) % cohort_size) + parity_offset
    cycle = same_parity_slot // cohort_size
    limit = int(rotation.get("max_categories_checked_per_slot", 5))
    if not (1 <= limit <= len(categories)//2):
        raise ValueError("Invalid category retry limit")
    brand_limit = int(rotation.get("max_brands_checked_per_category", 2))
    if not (1 <= brand_limit <= 4):
        raise ValueError("Invalid brand retry limit")
    candidates = []
    for distance in range(limit):
        entry = categories[(index + 2 * distance) % len(categories)]
        category = str(entry["site_slug"]).strip()
        budgets = [int(v) for v in entry["budgets"]]
        if not budgets or len(set(budgets)) != len(budgets) or any(v < 100 for v in budgets):
            raise ValueError("Invalid budget ladder for " + category)
        # Each category revisits after 10 dates of its own parity, with a
        # new primary price tier. Even dates start one tier ahead of odd.
        # Try every configured tier, then a deterministic unrounded amount within
        # the same category's configured minimum/maximum budget range.
        # This keeps the ad reproducible on catch-up runs, not randomly changing.
        selected = (cycle + parity_offset) % len(budgets)
        amounts = [budgets[(selected + i) % len(budgets)] for i in range(len(budgets))]
        low, high = min(budgets), max(budgets)
        if high - low > 2:
            seed = f"{day.isoformat()}|{mode}|{category}|{slot}"
            intermediate = low + 1 + (int(hashlib.sha256(seed.encode()).hexdigest()[:12], 16) % (high - low - 1))
            if intermediate not in amounts:
                amounts.insert(1, intermediate)
        if mode == "brand_budget":
            brands = [str(b).strip() for b in entry.get("brands", []) if str(b).strip()]
            if not brands:
                continue
            start = cycle % len(brands)
            for j in range(min(brand_limit, len(brands))):
                brand = brands[(start + j) % len(brands)]
                for budget in amounts:
                    candidates.append({"category":category, "budget":budget, "brand":brand})
        else:
            for budget in amounts:
                candidates.append({"category":category, "budget":budget, "brand":""})
    return candidates


def choose_campaign(mode, policy, *, day, slot=0, overrides=None, fetcher=build_site_ads_payload):
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
        candidates = rotation_candidates(mode, policy, day, slot=slot)
        if candidates is None:
            candidates = list(policy["campaigns"][mode])
            if not candidates:
                raise ValueError("Empty campaign schedule")
            offset = day.toordinal() % len(candidates)
            candidates = candidates[offset:] + candidates[:offset]

    failures = []
    max_attempts = int((policy.get("rotation") or {}).get("max_website_attempts_per_run", 48))
    if not 1 <= max_attempts <= 120:
        raise ValueError("Invalid website attempt limit")
    for candidate in candidates[:max_attempts]:
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
                "status": "eligible", "mode": mode, "slot": slot, "date_ist": day.isoformat(),
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
    return {"status":"no_eligible_campaign","mode":mode,"slot":slot,"date_ist":day.isoformat(),
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
    if report.get("campaign_mode") not in (None, plan["mode"]):
        raise ValueError("Rendered ad type does not match selected budget/brand/comparison mode")
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


def caption_for(plan, landing_url, *, network="instagram"):
    """Distinct honest CTAs for organic Instagram, Facebook and LinkedIn.

    All URLs and brand/budget claims must match the same site-approved
    campaign. A text CTA never pretends to be a paid Meta CTA button.
    """
    if network not in ("instagram", "facebook", "linkedin"):
        raise ValueError("Unsupported organic social network")
    mode = plan.get("mode")
    if mode not in MODES:
        raise ValueError("Unsupported campaign mode")
    category_slug = str(plan.get("category") or "").strip()
    category = category_slug.replace("-", " ").title()
    brand = str(plan.get("brand") or "").strip()
    budget_inr = int(plan["budget"])
    if budget_inr <= 0 or not category_slug:
        raise ValueError("Invalid campaign budget or category")
    if mode == "brand_budget" and not brand:
        raise ValueError("Brand-only campaign requires a brand")
    link = urlsplit(str(landing_url or ""))
    q = parse_qs(link.query)
    if (link.scheme != "https" or link.hostname not in ("trustfolio.in", REPO_HOST)
            or link.path != "/category/" + category_slug + "/products"
            or q.get("category", [category_slug])[0] != category_slug
            or q.get("budget") != [str(budget_inr)]
            or q.get("brand", [""])[0] != (brand if mode == "brand_budget" else "")):
        raise ValueError("Social caption URL does not match real category, budget and brand")
    amount = f"₹{budget_inr:,}"
    if mode == "brand_budget":
        title = f"Best {brand} {category} Under {amount}!"
        body = (f"{brand} ke website-ranked Top 5 options dekho. "
                "Listed prices aur specifications compare karke choose karo.")
    elif mode == "comparison":
        title = f"Compare Top 5 {category} Under {amount}!"
        body = ("5 alag-alag products ka side-by-side comparison dekho. "
                "Alag models ko ek hi product ki price saving nahi bataya ja raha.")
    else:
        title = f"Best {category} Under {amount}!"
        body = ("Apne budget ke 5 website-ranked options ek jagah dekho. "
                "Prices, features aur retailer options compare karo.")
    cta = "🚀 Apna budget daalo, Best 5 paao!"
    if network == "instagram":
        action = (f"🔎 Top 5 dekho (link copy karo): {landing_url}\n"
                  "Instagram feed links tappable nahi hote; profile par website link "
                  "available ho to wahan se open karo.")
    else:
        action = f"👉 Shop / Compare Now — Top 5 dekho: {landing_url}"
    tags = "#TrustFolio #SmartShopping #ProductComparison #BestDealsIndia"
    return (f"✨ {title}\n\n{body}\n\n{cta}\n{action}\n\n"
            "📲 TrustFolio Android App: "
            "https://play.google.com/store/apps/details?id=com.trustfolio.app\n"
            "Prices, availability aur ranking badal sakte hain; "
            "buy karne se pehle retailer par confirm karo.\n\n"
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
    p.add_argument("--slot",type=int,choices=(0,1),default=0,
                   help="Second daily slot uses different odd/even category and budget")
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
        plan=choose_campaign(args.mode,policy,day=args.day,slot=args.slot,overrides=overrides)
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
