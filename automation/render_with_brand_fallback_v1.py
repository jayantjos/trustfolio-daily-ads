"""Retry a failed VPS render with a different VERIFIED candidate of the same mode.

Runs on the GitHub runner; only the existing ads VPS folder is touched.
No Meta operations, publishing or database writes occur here.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from automation.auto_campaign_v1 import choose_campaign
from site_top5_ads_v1 import build_site_ads_payload

REMOTE_SCRIPT = """import json,sys
from pathlib import Path
key=sys.argv[1]
assert key.isdecimal()
root=Path.home()/'new_scraper'/'ads'
folder=root/'ads_qa'/'auto-runs'/key
plan=json.loads((folder/'plan.json').read_text('utf8'))
assert plan['status']=='eligible' and plan['account']=='trustfolio3'
sys.path.insert(0,str(root))
from ads_qa.render_site_ranked_qa_v1 import run
run(plan['category'],int(plan['budget']),plan['brand'],folder,mode=plan['mode'])
"""

def attempt_render(plan, *, run_key, folder, host, user, runner=subprocess.run):
    if host!="200.234.47.87" or user!="scraperuser":
        raise ValueError("Unknown deployment target; renderer cannot run")
    if not re.fullmatch(r"[0-9]+", str(run_key)):
        raise ValueError("Invalid GitHub run ID")
    if plan.get("status")!="eligible" or plan.get("mode") not in ("budget","brand_budget","comparison"):
        raise ValueError("Unapproved campaign plan")
    folder=Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder/"plan.json").write_text(json.dumps(plan,indent=2)+"\n",encoding="utf8")
    remote=f"{user}@{host}"
    remote_rel=f"new_scraper/ads/ads_qa/auto-runs/{run_key}"
    ssh=["ssh","-o","BatchMode=yes","-o","StrictHostKeyChecking=yes",remote]
    scp=["scp","-o","StrictHostKeyChecking=yes"]
    runner(ssh+[f'mkdir -p "$HOME/{remote_rel}"'],check=True,timeout=30)
    runner(scp+[str(folder/"plan.json"),f"{remote}:{remote_rel}/plan.json"],check=True,timeout=40)
    runner(ssh+[f'cd "$HOME/new_scraper/ads" && "$HOME/venv/bin/python" - {run_key}'],
           input=REMOTE_SCRIPT,text=True,check=True,timeout=280)
    for name in ("trustfolio-live-website-top5-1024x1536.png","website-top5-render-qa.json"):
        runner(scp+[f"{remote}:{remote_rel}/{name}",str(folder/name)],check=True,timeout=60)
    return json.loads((folder/"website-top5-render-qa.json").read_text("utf8"))


def select_alternative(plan, *, excluded, policy_path="automation/campaigns.json",
                       fetcher=build_site_ads_payload):
    policy=json.loads(Path(policy_path).read_text("utf8"))
    def filtered(category,budget,brand):
        if ((str(category),int(budget),str(brand or "")) in excluded
                or (str(category),int(budget),"*") in excluded):
            raise ValueError("Previously failed remote render")
        return fetcher(category,budget,brand)
    candidate=choose_campaign(plan["mode"],policy,day=plan["date_ist"],
                              slot=plan.get("slot",0),fetcher=filtered,
                              excluded_budget_pairs={(category,budget)
                                  for category,budget,brand in excluded if brand=="*"})
    if candidate.get("status")!="eligible":
        raise ValueError("No verified alternative after VPS render failed")
    return candidate


def render_with_fallback(plan, *, run_key, folder, host, user, max_renders=3,
                         renderer=attempt_render, selector=select_alternative,
                         excluded_budget_pairs=None):
    if not 1<=max_renders<=4:
        raise ValueError("Invalid bounded render attempts")
    excluded={(category,int(budget),"*") for category,budget
              in (excluded_budget_pairs or ())}
    current=dict(plan)
    for attempt in range(1,max_renders+1):
        print(f"REMOTE_RENDER_ATTEMPT={attempt}/{max_renders}",flush=True)
        try:
            report=renderer(current,run_key=run_key,folder=folder,host=host,user=user)
            from automation.auto_campaign_v1 import check_report
            check_report(current,report)
            return current,report
        except (subprocess.CalledProcessError,subprocess.TimeoutExpired,ValueError) as exc:
            # Errors are visible in the job log, but are not publication permission.
            print("REMOTE_RENDER_FAILED="+type(exc).__name__,flush=True)
            excluded.add((current["category"],int(current["budget"]),str(current.get("brand") or "")))
            if attempt==max_renders:
                raise
            current=selector(current,excluded=excluded)
            print("RENDER_FALLBACK_NEXT_VERIFIED_CATEGORY="+current["category"],flush=True)
    raise ValueError("Render retry budget exhausted")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--plan",default="campaign/plan.json")
    parser.add_argument("--folder",default="campaign")
    parser.add_argument("--run-key",required=True)
    parser.add_argument("--host",required=True)
    parser.add_argument("--user",required=True)
    parser.add_argument("--max-renders",type=int,default=3)
    parser.add_argument("--used-budgets-file",default="")
    args=parser.parse_args()
    plan=json.loads(Path(args.plan).read_text("utf8"))
    used=set()
    if args.used_budgets_file:
        data=json.loads(Path(args.used_budgets_file).read_text("utf8"))
        if data.get("generated_for")!=plan["date_ist"]:
            raise ValueError("Incorrect publication history date")
        used={(x["category"],int(x["budget"])) for x in data["used"]}
    selected,report=render_with_fallback(plan,run_key=args.run_key,folder=args.folder,
                              host=args.host,user=args.user,max_renders=args.max_renders,
                              excluded_budget_pairs=used)
    Path(args.plan).write_text(json.dumps(selected,indent=2)+"\n",encoding="utf8")
    print("REMOTE_RENDER_QA_AND_RANK_CHECK=PASS")
    print("FINAL_CAMPAIGN_ID="+selected["campaign_id"])
    print("FINAL_CATEGORY="+selected["category"])
    print("FINAL_BUDGET="+str(selected["budget"]))


if __name__=="__main__":
    main()
