"""Direct official Meta Graph publishing; no Metricool API subscription required.

Reads ONLY QA-passed, already hosted TrustFolio JPEG and caption.
Posts to the verified Instagram Professional account and linked Facebook Page.
All writes are OFF without explicitly configured GitHub Actions secrets and
TF_META_DIRECT_PUBLISH_ENABLED=true. Never edits website/app/scraper files.

Production properties:
* page and IG account identity preflight before every write
* exact public-media SHA256 check using the approved local file
* Instagram rolling 24-hour API publishing quota introspected at runtime
* conservative per-network daily cap + one GitHub reservation per campaign
* fail closed, no automatic retries after a possibly successful API request
* never duplicates already Metricool-scheduled October 17-25 ads
"""
import argparse
import base64
from datetime import date, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from automation.metricool_publish_v1 import _check_media
from automation.auto_campaign_v1 import caption_for

GRAPH_ORIGIN = "https://graph.facebook.com"
GITHUB_ORIGIN = "https://api.github.com/repos/jayantjos/trustfolio-daily-ads"
LEDGER_BRANCH = "trustfolio-meta-publishing-ledger"
EXPECTED_PAGE_ID = "619193294620746"
EXPECTED_IG_USERNAME = "trustfolio3"
REPO = "jayantjos/trustfolio-daily-ads"
IST = ZoneInfo("Asia/Kolkata")
DEFAULT_START_DATE = "2026-10-21"
NETWORKS = ("instagram", "facebook")


class PublishingBlocked(ValueError):
    """Preflight failed, without attempting Meta publication."""


def _request_json(url, token, *, method="GET", data=None, github=False):
    headers = {
        "Authorization": ("Bearer " if github else "Bearer ") + token,
        "Accept": "application/vnd.github+json" if github else "application/json",
        "User-Agent": "TrustFolioPublisher/1.0",
    }
    if github:
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    body = None
    if data is not None:
        if github:
            body = json.dumps(data).encode("utf8")
            headers["Content-Type"] = "application/json"
        else:
            body = urlencode(data).encode("utf8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=35) as response:
            raw = response.read(600_000)
            result = json.loads(raw) if raw else {}
            if not isinstance(result, (dict, list)):
                raise PublishingBlocked("Meta/GitHub response was not a JSON object")
            return result
    except HTTPError as error:
        # Include only stable Graph error codes, never provider-provided
        # messages, URLs, response headers, or access tokens.
        detail=""
        if not github:
            try:
                payload=json.loads(error.read(4096))
                graph_error=payload.get("error") or {}
                code=graph_error.get("code")
                subcode=graph_error.get("error_subcode")
                if type(code) is int:
                    detail+=" GRAPH_CODE="+str(code)
                if type(subcode) is int:
                    detail+=" GRAPH_SUBCODE="+str(subcode)
            except (ValueError,TypeError,AttributeError,OSError):
                pass
        raise PublishingBlocked(
            ("GitHub" if github else "Meta") +
            " REST operation failed: HTTP " + str(error.code)+detail
        ) from None


def _graph(version, path, token, *, fields=None, post=None):
    if not re.fullmatch(r"v[0-9]{1,2}\.[0-9]", version):
        raise PublishingBlocked("Invalid pinned Meta Graph API version")
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", path):
        raise PublishingBlocked("Invalid Meta Graph object route")
    url = GRAPH_ORIGIN + "/" + version + "/" + path
    if fields:
        url += "?" + urlencode({"fields":fields})
    return _request_json(url, token, method="POST" if post is not None else "GET",data=post)


def _github(token, path, *, method="GET", data=None):
    return _request_json(GITHUB_ORIGIN + "/" + path,token,method=method,data=data,github=True)


def load_env(*, env=None):
    env = env if env is not None else os.environ
    if env.get("TF_META_DIRECT_PUBLISH_ENABLED") != "true":
        raise PublishingBlocked("Direct Meta publishing is OFF; QA artifacts are still generated")
    if env.get("TF_AUTO_POST_ENABLED") == "true":
        raise PublishingBlocked("Old Metricool publishing and direct Meta cannot both be enabled")
    if env.get("GITHUB_REPOSITORY") != REPO:
        raise PublishingBlocked("Wrong GitHub repository for publication ledger")
    token = env.get("TF_META_PAGE_ACCESS_TOKEN") or ""
    gh = env.get("GITHUB_TOKEN") or ""
    if len(token) < 20 or len(gh) < 20:
        raise PublishingBlocked("Missing Meta Page access token or GitHub ledger token")
    if env.get("TF_META_PAGE_ID",EXPECTED_PAGE_ID) != EXPECTED_PAGE_ID:
        raise PublishingBlocked("Facebook Page ID does not match verified TrustFolio Page")
    version = env.get("TF_META_GRAPH_VERSION", "v25.0")
    if not re.fullmatch(r"v[0-9]{1,2}\.[0-9]", version):
        raise PublishingBlocked("Invalid pinned Meta Graph version")
    day = datetime.now(IST).date()
    start = date.fromisoformat(env.get("TF_META_START_DATE",DEFAULT_START_DATE))
    if day < start:
        raise PublishingBlocked("Direct Meta crossposting starts 2026-10-21")
    raw_networks = (env.get("TF_META_POST_NETWORKS") or "instagram,facebook").split(",")
    networks = tuple(x.strip().lower() for x in raw_networks if x.strip())
    if not networks or len(networks)!=len(set(networks)) or any(x not in NETWORKS for x in networks):
        raise PublishingBlocked("Unsupported/duplicate social network selection")
    max_posts = int(env.get("TF_META_MAX_POSTS_PER_DAY_PER_NETWORK","2"))
    if not (1 <= max_posts <= 20):
        raise PublishingBlocked("Local posting cap must be between 1 and 20")
    return {"page_token":token,"github_token":gh,"page_id":EXPECTED_PAGE_ID,
            "version":version,"networks":networks,"max_posts":max_posts,
            "today":day.isoformat()}


def validate_approved_manifest(manifest):
    if not isinstance(manifest,dict) or manifest.get("status")!="ready_for_publishing_gate":
        raise PublishingBlocked("This campaign lacks approved rendered-image QA")
    if manifest.get("publication_status")!="not_published":
        raise PublishingBlocked("Campaign has been published or is not ready")
    if manifest.get("instagram_account")!=EXPECTED_IG_USERNAME:
        raise PublishingBlocked("Campaign Instagram account is not @trustfolio3")
    if manifest.get("source_renderer")!="master_template_renderer_html_v4":
        raise PublishingBlocked("Not rendered by the approved premium template")
    if manifest.get("size")!=[1080,1350] or manifest.get("geometry_errors")!=[]:
        raise PublishingBlocked("Instagram dimension or geometry QA failed")
    ids=manifest.get("ranked_product_ids")
    if not isinstance(ids,list) or len(ids)!=5 or len(set(ids))!=5 or not all(ids):
        raise PublishingBlocked("Missing/duplicated website Top-5 ranked product IDs")
    key=str(manifest.get("campaign_id") or "")
    if not re.fullmatch(r"tfauto-[0-9a-f]{18}",key):
        raise PublishingBlocked("Invalid deterministic campaign id")
    landing=urlsplit(str(manifest.get("landing_url") or ""))
    if landing.scheme!="https" or landing.hostname not in ("trustfolio.in","www.trustfolio.in"):
        raise PublishingBlocked("Unverified landing URL domain")
    if not landing.path.startswith("/category/") or not landing.path.endswith("/products"):
        raise PublishingBlocked("Wrong budget-filtered product page")
    caption=manifest.get("caption") or ""
    if not (50<=len(caption)<=2100) or "play.google.com/store/apps/details?id=com.trustfolio.app" not in caption:
        raise PublishingBlocked("No verified caption/app link or exceeds conservative Instagram limit")
    return key


def confirm_page_token_type(cfg):
    """Read-only: /me must resolve to the expected Facebook Page, not a user.

    A User token can read Page+IG data after permissions are granted; do
    not confuse that with a Page token for unattended Page publishing.
    """
    me=_graph(cfg["version"],"me",cfg["page_token"],fields="id,name")
    if str(me.get("id") or "")!=cfg["page_id"]:
        raise PublishingBlocked("Token is not the Trustfolio Page token: /me did not return verified Facebook Page ID")
    return cfg["page_id"]


def confirm_page_identity(cfg):
    """Resolve IG ID through verified FB Page, never from guessed usernames."""
    p=_graph(cfg["version"],cfg["page_id"],cfg["page_token"],
             fields="id,name,instagram_business_account")
    if str(p.get("id")) != cfg["page_id"]:
        raise PublishingBlocked("Meta Page ID mismatch")
    ref=p.get("instagram_business_account") or {}
    igid=str(ref.get("id") or "")
    if not re.fullmatch(r"[0-9]+",igid):
        raise PublishingBlocked("Connect the @trustfolio3 Professional IG account to this Meta Page")
    i=_graph(cfg["version"],igid,cfg["page_token"],fields="id,username")
    if str(i.get("id"))!=igid or str(i.get("username") or "").lstrip("@").casefold()!=EXPECTED_IG_USERNAME:
        raise PublishingBlocked("Meta linked Instagram account is not @trustfolio3")
    return igid


def check_instagram_quota(cfg, igid):
    """Read live Meta limits, whose total/duration are nested under config.

    Graph's default response may only contain quota_usage; explicitly request
    config so we can refuse publication if the account-specific limit is absent.
    """
    r=_graph(cfg["version"],igid+"/content_publishing_limit",
             cfg["page_token"],fields="quota_usage,config")
    try:
        stats=r["data"][0]
        usage=int(stats["quota_usage"])
        config=stats["config"]
        total=int(config["quota_total"])
        duration=int(config["quota_duration"])
    except (TypeError,KeyError,ValueError,IndexError):
        raise PublishingBlocked("Instagram content publishing quota unreadable; no post attempted") from None
    if total <= 0 or duration <= 0 or usage < 0 or usage >= total:
        raise PublishingBlocked("Instagram rolling 24-hour publishing limit reached")
    return {"quota_usage":usage,"quota_total":total,"quota_duration":duration}


def ensure_ledger(cfg):
    token=cfg["github_token"]
    try:
        _github(token,"git/ref/heads/"+LEDGER_BRANCH)
        return
    except PublishingBlocked as exc:
        if "HTTP 404" not in str(exc):
            raise
    head=_github(token,"git/ref/heads/main")
    sha=(head.get("object") or {}).get("sha")
    if not re.fullmatch(r"[a-f0-9]{40}",str(sha or "")):
        raise PublishingBlocked("Cannot locate main branch HEAD for GitHub publication audit")
    try:
        _github(token,"git/refs",method="POST",data={"ref":"refs/heads/"+LEDGER_BRANCH,"sha":sha})
    except PublishingBlocked as exc:
        if "HTTP 422" not in str(exc):
            raise


def ledger_path(cfg,network,key):
    # One immutable publication slot per mode/network/date, regardless of which
    # eligible category or budget a later catch-up may select.
    mode = cfg.get("campaign_mode")
    name = (network+"-mode-"+mode+".json") if mode in ("budget","brand_budget","comparison") else (network+"-"+key+".json")
    return "meta-publication-ledger/"+cfg["today"]+"/"+name


def ledger_list(cfg):
    try:
        files=_github(cfg["github_token"],
                      "contents/meta-publication-ledger/"+cfg["today"]+"?"+
                      urlencode({"ref":LEDGER_BRANCH}))
    except PublishingBlocked as e:
        if "HTTP 404" in str(e):
            return []
        raise
    if not isinstance(files,list):
        raise PublishingBlocked("Invalid GitHub ledger directory response")
    return files


def reserve(cfg, network, key, url, *, max_posts):
    """One create-only GitHub contents write is an atomic no-duplicate lock.

    A reservation stays even after a failed/ambiguous Meta API response.
    Never blindly retry without checking Instagram/Facebook publication.
    """
    ensure_ledger(cfg)
    name=ledger_path(cfg,network,key).rsplit("/",1)[-1]
    current=ledger_list(cfg)
    if any(x.get("name")==name for x in current):
        if cfg.get("campaign_mode"):
            # A reserved/ambiguous API attempt is not proof of publication.
            # Never blindly retry it; successful posts can safely be skipped.
            previous=_github(cfg["github_token"],
                             "contents/"+ledger_path(cfg,network,key)+"?"+
                             urlencode({"ref":LEDGER_BRANCH}))
            try:
                item=json.loads(base64.b64decode(previous["content"]).decode("utf8"))
            except (KeyError,TypeError,ValueError):
                raise PublishingBlocked("Unreadable existing mode reservation; reconcile before retry") from None
            if item.get("status")=="api_accepted_published":
                return None
            # Exact historical recovery: with this publisher, /media_publish can
            # only run AFTER record_status(container_created) succeeds. Therefore
            # a durable 'reserved' record without a container status has not
            # reached the public-post write. Older failed Oct 27 IG attempts can
            # be safely reused after the original 25-min job has exited.
            # Any container_created or ambiguous post-publish state remains locked.
            if (network=="instagram" and item.get("status")=="reserved"
                    and not item.get("container_id")
                    and item.get("mode")==cfg.get("campaign_mode")):
                try:
                    since=datetime.fromisoformat(item["reserved_at"])
                    if since.tzinfo is None:
                        raise ValueError("Timezone missing")
                    eligible=datetime.now(IST)-since>=timedelta(minutes=45)
                except (KeyError,TypeError,ValueError):
                    eligible=False
                if eligible:
                    old_sha=previous.get("sha")
                    if not re.fullmatch(r"[a-f0-9]{40}",str(old_sha or "")):
                        raise PublishingBlocked("No safe GitHub version for reservation recovery")
                    now=datetime.now(IST).isoformat()
                    recovered={
                        "campaign_id":key,"network":network,
                        "mode":cfg["campaign_mode"],"status":"reserved",
                        "public_media_url":url,"reserved_at":now,
                        "recovered_from":item.get("campaign_id"),
                        "recovered_at":now
                    }
                    payload={
                        "branch":LEDGER_BRANCH,"sha":old_sha,
                        "message":"Safely reclaim prepublication Instagram mode "+
                                  cfg["campaign_mode"],
                        "content":base64.b64encode(
                            (json.dumps(recovered,sort_keys=True,indent=2)+"\n").encode()
                        ).decode()
                    }
                    try:
                        result=_github(cfg["github_token"],
                                       "contents/"+ledger_path(cfg,network,key),
                                       method="PUT",data=payload)
                    except PublishingBlocked as error:
                        if "HTTP 409" in str(error) or "HTTP 422" in str(error):
                            raise PublishingBlocked(
                                "Instagram reservation changed during recovery; retry read-only") from None
                        raise
                    new_sha=(result.get("content") or {}).get("sha")
                    if not re.fullmatch(r"[a-f0-9]{40}",str(new_sha or "")):
                        raise PublishingBlocked("Could not verify reclaimed Instagram reservation")
                    return new_sha
            raise PublishingBlocked("Prior "+network+" "+cfg["campaign_mode"]+
                                    " reservation is pending reconciliation")
        return None
    used=sum(x.get("name","").startswith(network+"-") for x in current)
    if used>=max_posts:
        raise PublishingBlocked("Own daily "+network+" cap already reached")
    result={
        "campaign_id":key, "network":network, "status":"reserved",
        "public_media_url":url, "reserved_at":datetime.now(IST).isoformat(),
    }
    if cfg.get("campaign_mode"):
        result["mode"]=cfg["campaign_mode"]
    data={
        "branch":LEDGER_BRANCH,
        "message":"Reserve Meta "+network+" campaign "+key,
        "content":base64.b64encode(
            (json.dumps(result,indent=2,sort_keys=True)+"\n").encode()).decode()
    }
    try:
        created=_github(cfg["github_token"],"contents/"+ledger_path(cfg,network,key),
                        method="PUT",data=data)
    except PublishingBlocked as e:
        if "HTTP 422" in str(e) or "HTTP 409" in str(e):
            return None
        raise
    sha=(created.get("content") or {}).get("sha")
    if not re.fullmatch("[a-f0-9]{40}",str(sha or "")):
        raise PublishingBlocked("Failed to reserve and verify GitHub campaign lock")
    return sha


def record_status(cfg,network,key,sha,status,extra=None):
    if not re.fullmatch(r"[a-f0-9]{40}",str(sha or "")):
        raise PublishingBlocked("Ledger SHA invalid")
    value={"campaign_id":key,"network":network,"status":status,
           "recorded_at":datetime.now(IST).isoformat()}
    if cfg.get("campaign_mode"):
        value["mode"]=cfg["campaign_mode"]
    value.update(extra or {})
    # Publish only verified campaign metadata, for cross-day category+budget
    # deduplication. Prior records lacking these fields are SHA-resolved.
    if status=="api_accepted_published" and cfg.get("campaign_metadata"):
        value.update(cfg["campaign_metadata"])
    obj={"branch":LEDGER_BRANCH,"sha":sha,
         "message":"Meta "+network+" campaign "+key+" "+status,
         "content":base64.b64encode(
             (json.dumps(value,indent=2,sort_keys=True)+"\n").encode()).decode()}
    r=_github(cfg["github_token"],"contents/"+ledger_path(cfg,network,key),
              method="PUT",data=obj)
    return (r.get("content") or {}).get("sha")


def prepare_instagram_media(cfg,igid,url,caption):
    """Create & finish a PRIVATE Instagram container before locking a public post.

    /media does not publish a feed post. If it fails, there must be no
    reservation; a later cron can safely try again.
    """
    creation=_graph(cfg["version"],igid+"/media",cfg["page_token"],
                    post={"image_url":url,"caption":caption})
    container=str(creation.get("id") or "")
    if not re.fullmatch(r"[0-9]+",container):
        raise PublishingBlocked("Meta did not return valid Instagram media container")
    for _ in range(8):
        stat=_graph(cfg["version"],container,cfg["page_token"],fields="status_code")
        status=stat.get("status_code")
        if status=="FINISHED":
            return container
        if status in ("ERROR","EXPIRED","PUBLISHED"):
            raise PublishingBlocked("Meta Instagram container status: "+str(status))
        time.sleep(4)
    raise PublishingBlocked("Meta Instagram container did not finish processing")


def publish_instagram(cfg,igid,url,caption,network,key,sha,*,prepared_container=None):
    container=prepared_container or prepare_instagram_media(cfg,igid,url,caption)
    # Publishing is forbidden until this ledger transition is confirmed.
    # A later retry may only reclaim a stale 'reserved' lock, never
    # 'container_created' (public media_publish may have been accepted).
    sha=record_status(cfg,network,key,sha,"container_created",
                      {"container_id":container})
    published=_graph(cfg["version"],igid+"/media_publish",cfg["page_token"],
                     post={"creation_id":container})
    mediaid=str(published.get("id") or "")
    if not re.fullmatch(r"[0-9]+",mediaid):
        raise PublishingBlocked("Meta returned no Instagram media ID; check before retry")
    record_status(cfg,network,key,sha,"api_accepted_published",
                  {"meta_media_id":mediaid,"container_id":container})
    return {"network":network,"status":"api_accepted_published","media_id":mediaid}


def publish_facebook(cfg,url,caption,network,key,sha):
    # /photos creates an image post on the linked Page. Include landing
    # URL in caption; Facebook makes normal URLs clickable.
    result=_graph(cfg["version"],cfg["page_id"]+"/photos",cfg["page_token"],
                  post={"url":url,"message":caption,"published":"true"})
    photoid=str(result.get("id") or result.get("post_id") or "")
    if not re.fullmatch(r"[0-9_]+",photoid):
        raise PublishingBlocked("Meta returned no Facebook photo/post ID; check Page before retry")
    record_status(cfg,network,key,sha,"api_accepted_published",
                  {"meta_photo_or_post_id":photoid})
    return {"network":network,"status":"api_accepted_published","media_id":photoid}


def network_caption(manifest, network):
    """Derive platform-specific CTA from verified campaign metadata.

    The same source image, ranked IDs and filtered landing URL are preserved;
    do not silently substitute a different product or brand.
    """
    try:
        plan={"mode":manifest["mode"],"category":manifest["category"],
              "budget":manifest["budget_inr"],"brand":manifest.get("brand") or ""}
        result=caption_for(plan,manifest["landing_url"],network=network)
    except (KeyError,TypeError,ValueError) as exc:
        raise PublishingBlocked("Social CTA does not match approved campaign filters") from exc
    if not (50<=len(result)<=2100):
        raise PublishingBlocked("Platform social CTA exceeds approved caption limit")
    return result


def publish_verified(manifest,media_url,local_jpg,*,env=None):
    key=validate_approved_manifest(manifest)
    captions={n:network_caption(manifest,n) for n in ("instagram","facebook")}
    cfg=load_env(env=env)
    mode=manifest.get("mode")
    if mode not in ("budget","brand_budget","comparison"):
        raise PublishingBlocked("Missing valid campaign mode for daily publication lock")
    cfg["campaign_mode"]=mode
    cfg["campaign_metadata"]={
        "category":manifest["category"],
        "budget_inr":int(manifest["budget_inr"]),
        "brand":manifest.get("brand") or "",
    }
    # Common preflight must succeed before attempting either network.
    _check_media(media_url,local_jpg)
    confirm_page_token_type(cfg)
    # Instagram connection failures must not prevent a valid Facebook post.
    igid=None
    ig_error=None
    if "instagram" in cfg["networks"]:
        try:
            igid=confirm_page_identity(cfg)
        except (PublishingBlocked, URLError, TimeoutError, OSError) as error:
            ig_error=str(error)
    results=[]
    for network in cfg["networks"]:
        try:
            if network=="instagram":
                if igid is None:
                    raise PublishingBlocked("Instagram identity preflight blocked: "+str(ig_error))
                quota=check_instagram_quota(cfg,igid)
                if quota["quota_usage"]>=quota["quota_total"]:
                    raise PublishingBlocked("No Instagram quota")
            prepared=None
            if network=="instagram":
                # The container creation and processing checks are non-public.
                # Do not strand the mode's reservation on a failed /media call.
                prepared=prepare_instagram_media(cfg,igid,media_url,captions["instagram"])
            sha=reserve(cfg,network,key,media_url,max_posts=cfg["max_posts"])
            if sha is None:
                results.append({"network":network,"status":"already_published_no_duplicate"})
                continue
            if network=="instagram":
                results.append(publish_instagram(cfg,igid,media_url,captions["instagram"],
                                                 network,key,sha,
                                                 prepared_container=prepared))
            else:
                results.append(publish_facebook(cfg,media_url,captions["facebook"],
                                                network,key,sha))
        except (PublishingBlocked, URLError, TimeoutError, OSError) as error:
            # A reservation made before a possibly accepted Meta write remains
            # locked; the next recovery run flags it for reconciliation.
            results.append({"network":network,"status":"blocked","reason":str(error)})
    return results


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--manifest",required=True)
    parser.add_argument("--jpg",required=True)
    parser.add_argument("--media-url",required=True)
    parser.add_argument("--preflight-only",action="store_true")
    args=parser.parse_args()
    m=json.loads(Path(args.manifest).read_text("utf8"))
    key=validate_approved_manifest(m)
    if args.preflight_only:
        _check_media(args.media_url,args.jpg)
        print("META_LOCAL_QA_MEDIA_VERIFIED="+key)
        print("META_PUBLISH_ATTEMPTED=NO")
        return
    results=publish_verified(m,args.media_url,args.jpg)
    # Never print OAuth secrets or raw Graph HTTP responses.
    for r in results:
        print("META_RESULT="+r["network"]+":"+r["status"])
        if r.get("media_id"):
            print("META_POST_OBJECT_ID="+r["media_id"])
        if r.get("reason"):
            print("META_POST_BLOCKED_REASON="+r["network"]+":"+r["reason"])
    if any(r["status"]=="blocked" for r in results):
        raise SystemExit("META_PARTIAL_PUBLICATION_FAILURE=YES")


if __name__=="__main__":
    main()
