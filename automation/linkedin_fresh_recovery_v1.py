"""Build a fresh LinkedIn-only campaign after the original Meta poster drifts.

Always require same-day, both-network Meta publication evidence for the
original campaign. Never call Meta publishing or alter Meta publication ledgers.
"""
import argparse
import json
import re
from pathlib import Path
from shutil import copytree

from automation.linkedin_x_crosspost_v1 import (
    check_meta_success, validate_source, ExtraSocialBlocked,
)
from automation.rebuild_stale_meta_campaign_v1 import rebuild_until_stable
from automation.verify_price_before_meta_publish_v1 import verify_fresh_snapshot

def recover(source, destination, *, token, run_key, host, user,
            builder=rebuild_until_stable):
    source=Path(source)
    destination=Path(destination)
    if source.resolve()==destination.resolve():
        raise ExtraSocialBlocked("Cannot overwrite original Meta campaign")
    if not token:
        raise ExtraSocialBlocked("GitHub Meta ledger authentication missing")
    if not re.fullmatch(r"[0-9]+",str(run_key)):
        raise ExtraSocialBlocked("Invalid isolated recovery run key")
    original,_,_=validate_source(source,verify_live=False)
    check_meta_success(token,original)
    plans=list(source.rglob("plan.json"))
    if len(plans)!=1:
        raise ExtraSocialBlocked("Expected exactly one original plan")
    plan=json.loads(plans[0].read_text("utf8"))
    if (plan.get("campaign_id")!=original["campaign_id"]
            or plan.get("mode")!=original["mode"]
            or plan.get("date_ist")!=original["date_ist"]):
        raise ExtraSocialBlocked("Original Meta campaign identity mismatch")
    if destination.exists():
        raise ExtraSocialBlocked("Recovery destination must be new")
    # Copy immutable source into an isolated working folder. The existing
    # renderer and price auditor generate and verify NEW media here.
    copytree(plans[0].parent,destination)
    selected,post,url=builder(
        plan,folder=destination,run_key=str(run_key),
        host=host,user=user,max_rebuilds=3)
    if (selected.get("date_ist")!=original["date_ist"]
            or selected.get("mode")!=original["mode"]):
        raise ExtraSocialBlocked("Recovered campaign changed authorized date/mode")
    report=json.loads((destination/"website-top5-render-qa.json").read_text("utf8"))
    verify_fresh_snapshot(selected,report)
    (destination/"linkedin-recovery-source.json").write_text(
        json.dumps({"meta_original":original,
                    "new_campaign_id":post["campaign_id"],
                    "source":"verified_same_day_meta_ledgers"},indent=2)+"\n",
        encoding="utf8")
    print("LINKEDIN_FRESH_RECOVERY_READY="+post["campaign_id"])
    print("LINKEDIN_FRESH_PUBLIC_URL="+url)
    return post

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",default="source-social-ad")
    p.add_argument("--destination",default="linkedin-fresh-ad")
    p.add_argument("--run-key",required=True)
    p.add_argument("--host",required=True)
    p.add_argument("--user",required=True)
    args=p.parse_args()
    import os
    recover(args.source,args.destination,token=os.getenv("GITHUB_TOKEN",""),
            run_key=args.run_key,host=args.host,user=args.user)

if __name__=="__main__":
    main()
