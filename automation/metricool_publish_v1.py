"""Metricool API scheduler with strict Instagram account, media and dedupe gates.

GitHub Actions cannot reuse the user's connected ChatGPT Metricool plugin token.
For unattended posts this module requires a separate Metricool REST API token
(available on Advanced/Custom accounts) stored ONLY in GitHub Actions Secrets.
Until TF_AUTO_POST_ENABLED=true and preflight passes, it makes no writes.
"""
import base64
import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from zoneinfo import ZoneInfo

METRICOOL_API="https://app.metricool.com/api"
GITHUB_API="https://api.github.com"
LEDGER_BRANCH="trustfolio-publishing-ledger"
EXPECTED_ACCOUNT="trustfolio3"
EXPECTED_BLOG="7271681"
EXPECTED_USER="5635852"
IST=ZoneInfo("Asia/Kolkata")


def _json_request(url, headers, *, method="GET", payload=None):
    body = json.dumps(payload).encode("utf8") if payload is not None else None
    options = dict(headers)
    if body is not None:
        options["Content-Type"]="application/json"
    with urlopen(Request(url, data=body,headers=options,method=method),timeout=30) as response:
        raw=response.read(500_000)
        if not raw:
            return {}
        return json.loads(raw)


def _require_env():
    if os.getenv("TF_AUTO_POST_ENABLED")!="true":
        raise ValueError("Posting disabled: TF_AUTO_POST_ENABLED is not true")
    blog=str(os.getenv("TF_METRICOOL_BLOG_ID",""))
    user=str(os.getenv("TF_METRICOOL_USER_ID",""))
    if blog!=EXPECTED_BLOG or user!=EXPECTED_USER:
        raise ValueError("Metricool brand IDs differ from verified TrustFolio account; do not post")
    token=os.getenv("TF_METRICOOL_API_TOKEN")
    if not token:
        raise ValueError("Missing TF_METRICOOL_API_TOKEN (requires supported Metricool API plan)")
    gh_token=os.getenv("GITHUB_TOKEN")
    if not gh_token or os.getenv("GITHUB_REPOSITORY")!="jayantjos/trustfolio-daily-ads":
        raise ValueError("GitHub ledger auth/repository missing")
    return blog,user,token,gh_token


def _identity_assertion(blog,user,token):
    data=_json_request(METRICOOL_API+"/admin/simpleProfiles?"+urlencode({"userId":user}),
        {"X-Mc-Auth":token,"Accept":"application/json"})
    profiles = data.get("data",data) if isinstance(data,(dict,list)) else None
    if isinstance(profiles,dict):
        profiles=profiles.get("data",profiles.get("profiles",[]))
    if not isinstance(profiles,list):
        raise ValueError("Metricool profile response format unknown; refuse to publish")
    for row in profiles:
        if not isinstance(row,dict):
            continue
        if str(row.get("blogId") or row.get("id") or "")!=blog:
            continue
        network=row.get("networksData") or {}
        instagram=network.get("instagramData") if isinstance(network,dict) else None
        if isinstance(instagram,dict):
            instagram=(instagram.get("username") or instagram.get("name"))
        if str(instagram or "").lstrip("@").casefold()==EXPECTED_ACCOUNT:
            return
    raise ValueError("Metricool API did not confirm blog's Instagram account @trustfolio3")


def _check_media(media_url, local_path):
    url=urlsplit(media_url)
    if url.scheme!="https" or url.hostname!="media.trustfolio.in" or not url.path.startswith("/trustfolio-auto/"):
        raise ValueError("Media must be permanent public TrustFolio HTTPS media")
    original=Path(local_path).read_bytes()
    if not original.startswith(b"\xff\xd8\xff"):
        raise ValueError("Source file is not a JPEG")
    with urlopen(Request(media_url,headers={"User-Agent":"TrustFolioMediaPreflight/1.0"}),timeout=25) as reply:
        if reply.status!=200:
            raise ValueError("Public image URL did not return 200")
        remote=reply.read(5_000_000)
    if hashlib.sha256(remote).digest()!=hashlib.sha256(original).digest():
        raise ValueError("Public URL image differs from QA-approved image")
    return True


def _find_media_id(value):
    if isinstance(value,dict):
        for key in ("mediaId","media_id","id"):
            candidate=value.get(key)
            if isinstance(candidate,(str,int)) and str(candidate).strip():
                return str(candidate)
        for key in ("data","result","media","image"):
            if key in value:
                nested=_find_media_id(value[key])
                if nested:
                    return nested
    if isinstance(value,list):
        for item in value:
            v=_find_media_id(item)
            if v:
                return v
    return None


def _normalize_media(url,blog,user,token):
    data=_json_request(METRICOOL_API+"/actions/normalize/image/url?"+
        urlencode({"url":url,"blogId":blog,"userId":user}),
        {"X-Mc-Auth":token,"Accept":"application/json"})
    media_id=_find_media_id(data)
    if not media_id:
        raise ValueError("Metricool normalize endpoint did not provide a media ID: no post created")
    return media_id


def _github_request(path, token, *, method="GET", payload=None):
    return _json_request(GITHUB_API+"/repos/jayantjos/trustfolio-daily-ads/"+path,
        {"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
         "X-GitHub-Api-Version":"2022-11-28"},method=method,payload=payload)


def _ensure_ledger(token):
    try:
        _github_request("git/ref/heads/"+LEDGER_BRANCH,token)
        return
    except HTTPError as exc:
        if exc.code!=404:
            raise
    head=_github_request("git/ref/heads/main",token)
    sha=head["object"]["sha"]
    try:
        _github_request("git/refs",token,method="POST",
            payload={"ref":"refs/heads/"+LEDGER_BRANCH,"sha":sha})
    except HTTPError as exc:
        if exc.code not in (409,422):
            raise


def _ledger_put(token, key, obj, *, sha=None):
    path="automation-ledger/"+key+".json"
    payload={
        "message":"TrustFolio Instagram campaign "+key+": "+obj["status"],
        "content":base64.b64encode((json.dumps(obj,sort_keys=True,indent=2)+"\n").encode()).decode(),
        "branch":LEDGER_BRANCH,
    }
    if sha:
        payload["sha"]=sha
    return _github_request("contents/"+path,token,method="PUT",payload=payload)


def _reserve_campaign(token, key, media_url):
    _ensure_ledger(token)
    path="contents/automation-ledger/"+key+".json?"+urlencode({"ref":LEDGER_BRANCH})
    try:
        existing=_github_request(path,token)
        if isinstance(existing,dict) and existing.get("sha"):
            return None
    except HTTPError as exc:
        if exc.code!=404:
            raise
    record={"campaign_id":key,"status":"reserved",
            "media_url":media_url,"reserved_at":datetime.now(IST).isoformat()}
    result=_ledger_put(token,key,record)
    return result["content"]["sha"]


def schedule_validated_post(manifest, media_url, local_path):
    if manifest.get("status")!="ready_for_publishing_gate" or manifest.get("publication_status")!="not_published":
        raise ValueError("Campaign not approved for scheduling")
    if manifest.get("network")!="instagram" or manifest.get("instagram_account")!=EXPECTED_ACCOUNT:
        raise ValueError("Target account is not @trustfolio3")
    if len(manifest.get("ranked_product_ids") or [])!=5 or manifest.get("geometry_errors")!=[]:
        raise ValueError("QA not clean; refuse to schedule")
    key=str(manifest.get("campaign_id") or "")
    if not key.startswith("tfauto-") or len(key)>48:
        raise ValueError("Invalid deterministic campaign ID")
    blog,user,token,gh_token=_require_env()
    _check_media(media_url,local_path)
    _identity_assertion(blog,user,token)
    media_id=_normalize_media(media_url,blog,user,token)
    sha=_reserve_campaign(gh_token,key,media_url)
    if sha is None:
        return {"status":"already_reserved_or_scheduled","campaign_id":key}
    when=datetime.now(IST)+timedelta(minutes=20)
    payload={
        "publicationDate":{"dateTime":when.strftime("%Y-%m-%dT%H:%M:%S"),"timezone":"Asia/Calcutta"},
        "text":str(manifest["caption"]),
        "providers":[{"network":"instagram"}],
        "instagramData":{"type":"POST","isAiGenerated":False},
        "media":{"mediaId":media_id},
        "autoPublish":True,
        "draft":False,
    }
    try:
        result=_json_request(METRICOOL_API+"/v2/scheduler/posts?"+
            urlencode({"blogId":blog,"userId":user}),
            {"X-Mc-Auth":token,"Accept":"application/json"},method="POST",payload=payload)
        if not isinstance(result,dict) or result.get("error"):
            raise ValueError("Metricool did not accept the scheduled post")
        posted=result.get("data",result)
        if not isinstance(posted,dict) or not (posted.get("id") or posted.get("uuid")):
            raise ValueError("Metricool response has no scheduling identifier; check planner before retry")
        record={"campaign_id":key,"status":"scheduled","media_url":media_url,
                "scheduled_at":when.isoformat(),"metricool_post_id":str(posted.get("id") or ""),
                "metricool_post_uuid":str(posted.get("uuid") or ""),
                "network":"instagram","handle":EXPECTED_ACCOUNT}
        _ledger_put(gh_token,key,record,sha=sha)
        return {"status":"scheduled","campaign_id":key,
                "metricool_post_id":record["metricool_post_id"],
                "scheduled_at":when.isoformat()}
    except Exception:
        # Do not delete reservation; a network timeout may follow a successful
        # Metricool write. This prevents duplicate posts on a retry.
        raise


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--manifest",required=True)
    parser.add_argument("--jpg",required=True)
    parser.add_argument("--media-url",required=True)
    args=parser.parse_args()
    manifest=json.loads(Path(args.manifest).read_text("utf8"))
    status=schedule_validated_post(manifest,args.media_url,args.jpg)
    print("METRICOOL_POST_RESULT="+status["status"])
    print("CAMPAIGN_ID="+status["campaign_id"])
    if "metricool_post_id" in status:
        print("METRICOOL_POST_ID="+status["metricool_post_id"])


if __name__=="__main__":
    main()
