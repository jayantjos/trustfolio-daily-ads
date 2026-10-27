"""Rebuild a newly stale TrustFolio ad, safely, before a Meta write.

The old JPG is never published after a ranking/price drift. Every rebuilt
creative gets a new content-addressed campaign identifier and public URL.
No database/app/scraper writes. A confirmed published mode is never retried.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

from automation.auto_campaign_v1 import package_assets
from automation.meta_graph_publish_v1 import validate_approved_manifest
from automation.metricool_publish_v1 import _check_media
from automation.render_with_brand_fallback_v1 import render_with_fallback
from automation.verify_price_before_meta_publish_v1 import verify_fresh_snapshot, PriceAuditBlocked

MEDIA_ROOT="https://media.trustfolio.in/trustfolio-auto/"

def refreshed_campaign_id(plan,report):
    raw=json.dumps({
        "original_campaign_id":plan["campaign_id"],"mode":plan["mode"],
        "category":plan["category"],"budget":plan["budget"],"brand":plan.get("brand") or "",
        "ranked_product_ids":report["visual_product_ids_by_rank"],
        "displayed_prices":report["displayed_prices_by_rank"],
        "price_sources":report["price_sources_by_rank"]
    },sort_keys=True,separators=(",",":"),ensure_ascii=False)
    return "tfauto-"+hashlib.sha256(raw.encode("utf8")).hexdigest()[:18]


def stage_verified_media(plan,report,*,folder,host,user,runner=subprocess.run,
                         media_check=_check_media):
    if host!="200.234.47.87" or user!="scraperuser":
        raise ValueError("Unknown public media deployment target")
    folder=Path(folder)
    fingerprint=refreshed_campaign_id(plan,report)
    plan=dict(plan,campaign_id=fingerprint)
    jpg,manifest=package_assets(plan,report,
                    folder/"trustfolio-live-website-top5-1024x1536.png",
                    folder/"post")
    validate_approved_manifest(manifest)
    remote=f"{user}@{host}"
    dest=f"public_media/trustfolio-auto/{fingerprint}.jpg"
    ssh=["ssh","-o","BatchMode=yes","-o","StrictHostKeyChecking=yes",remote]
    scp=["scp","-o","StrictHostKeyChecking=yes"]
    runner(ssh+['mkdir -p "$HOME/public_media/trustfolio-auto"'],check=True,timeout=30)
    runner(scp+[str(jpg),f"{remote}:{dest}"],check=True,timeout=70)
    runner(ssh+[f'chmod 644 "$HOME/{dest}"'],check=True,timeout=30)
    public_url=MEDIA_ROOT+jpg.name
    # Ensure the object actually served to Instagram is the approved media.
    # Fresh versioned name avoids cache collisions and stale campaign URLs.
    for check in range(3):
        try:
            media_check(public_url,str(jpg))
            break
        except (OSError,ValueError) as err:
            if check==2:
                raise ValueError("New JPEG not yet publicly identical to approved media") from err
            time.sleep(3)
    (folder/"plan.json").write_text(json.dumps(plan,indent=2)+"\n",encoding="utf8")
    print("REBUILT_PUBLIC_JPEG_SHA_VERIFIED="+jpg.name,flush=True)
    return plan,manifest,public_url


def rebuild_until_stable(plan, *, folder,run_key,host,user,max_rebuilds=2,
                         render=render_with_fallback,
                         stage=stage_verified_media,
                         audit=verify_fresh_snapshot):
    if not 1<=max_rebuilds<=3:
        raise ValueError("Unbounded ad refresh denied")
    current=dict(plan)
    for cycle in range(1,max_rebuilds+1):
        print("FRESH_AD_REBUILD_ATTEMPT="+str(cycle)+"/"+str(max_rebuilds),flush=True)
        current,report=render(current,run_key=run_key,folder=folder,host=host,user=user,
                              max_renders=2)
        current,manifest,url=stage(current,report,folder=folder,host=host,user=user)
        try:
            audit(current,report)
            print("META_PREPUBLISH_PRICE_PARITY=PASS_AFTER_REBUILD",flush=True)
            return current,manifest,url
        except PriceAuditBlocked as err:
            # Do not advertise outdated ranks/prices, even after rebuilding.
            print("FRESH_AD_REBUILD_STALE="+str(err),flush=True)
            if cycle==max_rebuilds:
                raise
    raise PriceAuditBlocked("No stable genuine website Top-5 snapshot found")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--folder",default="campaign")
    p.add_argument("--run-key",required=True)
    p.add_argument("--host",required=True)
    p.add_argument("--user",required=True)
    p.add_argument("--max-rebuilds",type=int,default=2)
    args=p.parse_args()
    if not re.fullmatch(r"[0-9]+",args.run_key):
        raise ValueError("Invalid workflow run ID")
    folder=Path(args.folder)
    plan=json.loads((folder/"plan.json").read_text("utf8"))
    result,manifest,url=rebuild_until_stable(
        plan,folder=folder,run_key=args.run_key,
        host=args.host,user=args.user,max_rebuilds=args.max_rebuilds)
    print("FINAL_CAMPAIGN_ID="+result["campaign_id"])
    print("FINAL_CAMPAIGN_MEDIA_URL="+url)
    print("PUBLICATION_STILL_PENDING_META=true")


if __name__=="__main__":
    main()
