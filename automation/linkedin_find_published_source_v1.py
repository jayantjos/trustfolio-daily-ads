"""Recover exact same-day Meta campaign source for independent LinkedIn catch-up.

Read both Meta ledgers, then inspect retained artifacts from successful Meta
workflow runs. Never assume latest scheduled run contains a real campaign.
"""
import argparse,base64,io,json,os,re,zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from zoneinfo import ZoneInfo

REPO="jayantjos/trustfolio-daily-ads"
BRANCH="trustfolio-meta-publishing-ledger"
MODES=("budget","brand_budget","comparison")
IST=ZoneInfo("Asia/Kolkata")

def gh(path,token,*,read_bytes=False):
    req=Request("https://api.github.com/repos/"+REPO+"/"+path,
       headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
                "User-Agent":"TrustFolio-LinkedIn-Recovery/1"})
    with urlopen(req,timeout=35) as res:
        raw=res.read(30000000 if read_bytes else 1500000)
    return raw if read_bytes else json.loads(raw)

def meta_identity(mode,day,token,fetch=gh):
    if mode not in MODES or not re.fullmatch(r"20\d{2}-\d{2}-\d{2}",day):
        raise ValueError("Invalid campaign mode/day")
    records=[]
    for network in ("instagram","facebook"):
        path=f"meta-publication-ledger/{day}/{network}-mode-{mode}.json"
        try:
            obj=fetch("contents/"+path+"?ref="+BRANCH,token)
        except HTTPError as err:
            if err.code==404:raise ValueError("Meta post missing: "+network) from None
            raise
        d=json.loads(base64.b64decode(obj["content"]))
        if (d.get("status")!="api_accepted_published" or d.get("network")!=network
                or d.get("mode")!=mode or not re.fullmatch(r"tfauto-[a-f0-9]{18}",str(d.get("campaign_id","")))):
            raise ValueError("Unverified Meta publication: "+network)
        records.append(d)
    if records[0]["campaign_id"]!=records[1]["campaign_id"]:
        raise ValueError("Different Meta campaign IDs for same mode")
    return records[0]["campaign_id"]

def source_candidates(token,fetch=gh):
    for page in range(1,6):
        data=fetch(f"actions/runs?per_page=100&page={page}",token)
        runs=data.get("workflow_runs",[])
        for run in runs:
            if (run.get("name")=="TrustFolio automated Instagram campaigns"
                and run.get("head_branch")=="main" and run.get("conclusion")=="success"
                and run.get("event") in ("schedule",)):
                yield run
        if len(runs)<100:break

def safe_extract(archive,target):
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        for info in z.infolist():
            p=Path(info.filename)
            if p.is_absolute() or ".." in p.parts or info.file_size>12000000:
                raise ValueError("Unsafe source artifact")
        z.extractall(target)

def locate(mode,day,token,destination,*,fetch=gh):
    campaign_id=meta_identity(mode,day,token,fetch=fetch)
    destination=Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Destination must be empty")
    for run in source_candidates(token,fetch=fetch):
        rid=run["id"]
        artifacts=fetch(f"actions/runs/{rid}/artifacts?per_page=100",token).get("artifacts",[])
        artifacts=[a for a in artifacts if a.get("name") in (
            f"trustfolio-social-final-{rid}",f"trustfolio-social-campaign-{rid}")
            and not a.get("expired")]
        artifacts.sort(key=lambda a:(not a["name"].startswith("trustfolio-social-final"),
                      -(int(a.get("id") or 0))))
        for a in artifacts:
            raw=fetch(f"actions/artifacts/{a['id']}/zip",token,read_bytes=True)
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                names=[n for n in z.namelist() if n.endswith("post.json")]
                if len(names)!=1:continue
                post=json.loads(z.read(names[0]))
                if (post.get("campaign_id")!=campaign_id or post.get("mode")!=mode
                        or post.get("date_ist")!=day):continue
            destination.mkdir(parents=True,exist_ok=True)
            safe_extract(raw,destination)
            print("LINKEDIN_EXACT_META_SOURCE_RUN="+str(rid))
            print("LINKEDIN_EXACT_META_SOURCE_ID="+campaign_id)
            return rid
    raise ValueError("No exact approved published Meta artifact available")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=MODES,required=True)
    p.add_argument("--output",default="source-social-ad")
    args=p.parse_args()
    token=os.getenv("GITHUB_TOKEN","")
    if not token:raise SystemExit("Missing GitHub token")
    day=datetime.now(IST).date().isoformat()
    locate(args.mode,day,token,args.output)

if __name__=="__main__":main()
