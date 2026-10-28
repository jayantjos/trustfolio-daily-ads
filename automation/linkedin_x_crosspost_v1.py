"""Independent, fail-closed TrustFolio LinkedIn + X image crossposting.

Source: immutable, QA-approved original IG/FB schedule artifact only.
Never changes Meta publishing, backend ranking, MongoDB or the source poster.
Default: OFF for both networks until owner explicitly configures OAuth + flags.
"""
import argparse
import base64
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
import uuid
from urllib.error import HTTPError,URLError
from urllib.parse import urlsplit,urlencode
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from automation.auto_campaign_v1 import check_report
from automation.meta_graph_publish_v1 import (_github,validate_approved_manifest,
                                               PublishingBlocked)
from automation.verify_price_before_meta_publish_v1 import (
    verify_fresh_snapshot,PriceAuditBlocked)
from automation.metricool_publish_v1 import _check_media

REPO="jayantjos/trustfolio-daily-ads"
LEDGER="trustfolio-extra-social-ledger"
IST=ZoneInfo("Asia/Kolkata")
MODES=("budget","brand_budget","comparison")
NETWORKS=("linkedin","x")
MEDIA_ROOT="https://media.trustfolio.in/trustfolio-auto/"

class ExtraSocialBlocked(ValueError):
    pass

def api_request(url,token,*,method="GET",payload=None,raw=None,content_type="application/json",
                extra_headers=None):
    headers={"Authorization":"Bearer "+token,"User-Agent":"TrustFolioExtraSocial/1.0",
             "Accept":"application/json"}
    if extra_headers:headers.update(extra_headers)
    body=json.dumps(payload).encode("utf8") if payload is not None else raw
    if body is not None: headers["Content-Type"]=content_type
    try:
        with urlopen(Request(url,data=body,headers=headers,method=method),timeout=35) as response:
            data=response.read(500_000)
            parsed=json.loads(data) if data else {}
            return response.status,parsed,dict(response.headers)
    except HTTPError as error:
        # Never include provider text, which might contain tokens/PII.
        raise ExtraSocialBlocked("Provider HTTP "+str(error.code)) from None
    except (URLError,TimeoutError,OSError):
        raise ExtraSocialBlocked("Provider connection failed") from None

def ensure_ledger(token):
    try: _github(token,"git/ref/heads/"+LEDGER);return
    except PublishingBlocked as exc:
        if "HTTP 404" not in str(exc): raise
    head=_github(token,"git/ref/heads/main")
    sha=(head.get("object") or {}).get("sha")
    if not re.fullmatch("[a-f0-9]{40}",str(sha)):raise ExtraSocialBlocked("Main ref missing")
    try: _github(token,"git/refs",method="POST",data={"ref":"refs/heads/"+LEDGER,"sha":sha})
    except PublishingBlocked as exc:
        if "HTTP 422" not in str(exc):raise

def get_ledger(token,branch,path):
    try:
        record=_github(token,"contents/"+path+"?"+urlencode({"ref":branch}))
    except PublishingBlocked as exc:
        if "HTTP 404" in str(exc):return None
        raise
    return json.loads(base64.b64decode(record["content"]).decode("utf8"))

def check_meta_success(token,manifest):
    day=manifest["date_ist"];mode=manifest["mode"];cid=manifest["campaign_id"]
    for network in ("instagram","facebook"):
        path=f"meta-publication-ledger/{day}/{network}-mode-{mode}.json"
        item=get_ledger(token,"trustfolio-meta-publishing-ledger",path)
        if not item or item.get("status")!="api_accepted_published" or item.get("campaign_id")!=cid:
            raise ExtraSocialBlocked("Cannot prove original campaign was published to both Meta networks")
    return True

def validate_source(folder,*,gh_token=None,verify_live=False):
    folder=Path(folder)
    posts=list(folder.rglob("post.json"))
    if len(posts)!=1:raise ExtraSocialBlocked("Expected exactly one approved post manifest")
    post=json.loads(posts[0].read_text("utf8"))
    try:validate_approved_manifest(post)
    except PublishingBlocked as exc:raise ExtraSocialBlocked(str(exc)) from None
    if post.get("mode") not in MODES:raise ExtraSocialBlocked("Unknown scheduled format")
    if post.get("date_ist")!=datetime.now(IST).date().isoformat():
        raise ExtraSocialBlocked("Crossposting older-day archives is disabled")
    candidate=posts[0].parent / (post["campaign_id"]+".jpg")
    if not candidate.is_file():raise ExtraSocialBlocked("Approved JPEG missing")
    jpg=candidate.read_bytes()
    if not (1000<len(jpg)<10_000_000 and jpg[:3]==b"\xff\xd8\xff"):
        raise ExtraSocialBlocked("Invalid or oversized JPEG")
    reports=list(folder.rglob("website-top5-render-qa.json"))
    plans=list(folder.rglob("plan.json"))
    if len(reports)!=1 or len(plans)!=1:
        raise ExtraSocialBlocked("Source QA snapshot or website plan missing")
    report=json.loads(reports[0].read_text("utf8"))
    plan=json.loads(plans[0].read_text("utf8"))
    if plan.get("campaign_id")!=post["campaign_id"]:
        raise ExtraSocialBlocked("Website candidate does not match caption/JPEG")
    check_report(plan,report)
    if post["ranked_product_ids"]!=report["visual_product_ids_by_rank"]:
        raise ExtraSocialBlocked("Mismatched visual Top-5 ranking")
    public_url=MEDIA_ROOT+post["campaign_id"]+".jpg"
    if verify_live:
        if not gh_token:raise ExtraSocialBlocked("Missing GitHub token for published-mode check")
        check_meta_success(gh_token,post)
        _check_media(public_url,str(candidate))
        try:verify_fresh_snapshot(plan,report)
        except PriceAuditBlocked as e:raise ExtraSocialBlocked("Website rankings/prices changed; no crosspost") from e
    return post,candidate,public_url

def ledger_path(network,post):
    if network not in NETWORKS or post["mode"] not in MODES:
        raise ExtraSocialBlocked("Invalid posting slot")
    return f"extra-social-ledger/{post['date_ist']}/{network}-mode-{post['mode']}.json"

def reserve_slot(token,network,post):
    """Immutable one-attempt lock. Never blindly retry ambiguous API errors."""
    ensure_ledger(token)
    path=ledger_path(network,post)
    if get_ledger(token,LEDGER,path) is not None:
        print("EXTRA_SOCIAL_DUPLICATE_SKIPPED="+network+":"+post["mode"])
        return None
    status={"network":network,"mode":post["mode"],
            "campaign_id":post["campaign_id"],"status":"reserved",
            "reserved_at":datetime.now(IST).isoformat()}
    try:
        _github(token,"contents/"+path,method="PUT",
                data={"message":"Reserve "+network+" "+post["mode"]+" before API upload",
                      "content":base64.b64encode(json.dumps(status).encode()).decode(),
                      "branch":LEDGER})
    except PublishingBlocked as e:
        if "HTTP 422" in str(e) or "HTTP 409" in str(e):
            print("EXTRA_SOCIAL_CONCURRENT_RESERVATION="+network)
            return None
        raise
    return path

def complete_slot(token,path,network,post,post_id):
    if not isinstance(post_id,str) or not post_id:
        raise ExtraSocialBlocked("API did not return a valid post ID")
    file=_github(token,"contents/"+path+"?"+urlencode({"ref":LEDGER}))
    old=json.loads(base64.b64decode(file["content"]).decode("utf8"))
    if old.get("status")!="reserved" or old.get("campaign_id")!=post["campaign_id"]:
        raise ExtraSocialBlocked("Reservation identity mismatched")
    old.update({"status":"api_accepted_published","external_post_id":post_id,
                "recorded_at":datetime.now(IST).isoformat()})
    _github(token,"contents/"+path,method="PUT",
            data={"message":"Crossposted "+network+" "+post["mode"],
                  "sha":file["sha"],"branch":LEDGER,
                  "content":base64.b64encode(json.dumps(old).encode()).decode()})

def linkedin_post_text(post):
    """Professional, per-mode LinkedIn caption for the original verified Top-5.

    No invented prices, benefits or reviews. LinkedIn supports a clickable
    landing URL, unlike the Instagram-only bio instructions in the source.
    """
    mode=post.get("mode")
    if mode not in MODES:
        raise ExtraSocialBlocked("Unsupported LinkedIn campaign mode")
    category=str(post.get("category") or "").replace("-", " ").title()
    try:
        budget=int(post["budget_inr"])
    except (KeyError,TypeError,ValueError):
        raise ExtraSocialBlocked("Invalid LinkedIn campaign budget") from None
    if budget<=0 or not category.strip():
        raise ExtraSocialBlocked("Invalid LinkedIn category/budget")
    brand=str(post.get("brand") or "").strip()
    if mode=="brand_budget" and not brand:
        raise ExtraSocialBlocked("Brand-only campaign is missing its brand")
    landing=str(post.get("landing_url") or "")
    url=urlsplit(landing)
    if (url.scheme!="https" or url.hostname not in ("trustfolio.in","www.trustfolio.in")
            or not url.path.endswith("/products")):
        raise ExtraSocialBlocked("LinkedIn link must use the original TrustFolio results page")
    from urllib.parse import parse_qs
    params=parse_qs(url.query)
    if (params.get("budget")!=[str(budget)]
            or (params.get("brand",[""])[0] if mode=="brand_budget" else "")!=
               (brand if mode=="brand_budget" else "")):
        raise ExtraSocialBlocked("LinkedIn caption filters do not match the approved poster")
    amount=f"₹{budget:,}"
    if mode=="budget":
        opening=f"{amount} tak ke budget mein {category} choose kar rahe hain?"
        details=("TrustFolio par is budget ke 5 website-ranked options ek jagah dekhein. "
                 "Prices aur specifications ko apni zaroorat ke hisaab se compare karein.")
    elif mode=="brand_budget":
        opening=f"{brand} {category} under {amount} — Top 5 options."
        details=(f"Sirf {brand} ke available website-ranked options dekhein aur "
                 "features aur listed prices ko ek jagah compare karein.")
    else:
        opening=f"{amount} ke andar {category}: 5 alag products ka comparison."
        details=("Alag-alag models ke prices aur specifications ko side-by-side dekhein. "
                 "Yeh alag products ka comparison hai, ek product par saving ka claim nahi.")
    return (f"✨ {opening}\n\n{details}\n\n"
            "🚀 Apna budget daalo, Best 5 paao!\n"
            f"👉 Explore / Compare Top 5: {landing}\n\n"
            "Prices, availability aur ranking badal sakte hain; "
            "kharidne se pehle retailer par confirm karein.\n\n"
            "#TrustFolio #SmartShopping #ProductComparison")


def linkedin_image_post(post,jpg,token,author,version="202608",requester=api_request):
    if not re.fullmatch(r"urn:li:(organization|person):[A-Za-z0-9_-]+",author):
        raise ExtraSocialBlocked("LinkedIn owner must be explicit verified person/company URN")
    if not re.fullmatch("202[6-9](0[1-9]|1[0-2])",version):
        raise ExtraSocialBlocked("Invalid LinkedIn API version")
    headers={"Linkedin-Version":version,"X-Restli-Protocol-Version":"2.0.0"}
    _,result,_=requester("https://api.linkedin.com/rest/images?action=initializeUpload",
            token,method="POST",payload={"initializeUploadRequest":{"owner":author}},
            extra_headers=headers)
    init=result.get("value") or {}
    url=init.get("uploadUrl") or ""
    host=urlsplit(url)
    if host.scheme!="https" or not (host.hostname=="linkedin.com" or str(host.hostname).endswith(".linkedin.com")):
        raise ExtraSocialBlocked("Unexpected LinkedIn upload host")
    urn=init.get("image") or ""
    if not re.fullmatch(r"urn:li:image:[A-Za-z0-9_-]+",urn):
        raise ExtraSocialBlocked("LinkedIn image URN missing")
    requester(url,token,method="PUT",raw=jpg.read_bytes(),content_type="image/jpeg",
              extra_headers={"Accept":"*/*"})
    _,_,h=requester("https://api.linkedin.com/rest/posts",token,method="POST",
        payload={"author":author,"commentary":linkedin_post_text(post),"visibility":"PUBLIC",
                 "distribution":{"feedDistribution":"MAIN_FEED","targetEntities":[],
                                 "thirdPartyDistributionChannels":[]},
                 "content":{"media":{"id":urn,"altText":"TrustFolio verified Top-5 products"}},
                 "lifecycleState":"PUBLISHED","isReshareDisabledByAuthor":False},
        extra_headers=headers)
    ident=h.get("x-restli-id") or h.get("X-RestLi-Id") or ""
    if not re.fullmatch(r"urn:li:(share|ugcPost):[0-9]+",str(ident)):
        raise ExtraSocialBlocked("LinkedIn post response lacks verifiable post identifier")
    return ident

def x_post_text(post):
    mode=post["mode"]
    kind={"budget":"Best picks","brand_budget":"Best brand picks",
          "comparison":"Top-5 comparison"}[mode]
    label=post["category"].replace("-"," ").title()
    brand=(" | "+post["brand"]) if mode=="brand_budget" else ""
    text=f"TrustFolio {kind}: {label}{brand} under ₹{post['budget_inr']:,}. Live Top-5 picks, prices & details:\n{post['landing_url']}"
    # X treats URLs as 23 weighted characters, but enforce a strict conservative 280-char cap too.
    if len(text)>280:raise ExtraSocialBlocked("X caption too long; no truncated or incorrect URL")
    return text

def x_image_post(post,jpg,token,expected_user_id,requester=api_request):
    if not re.fullmatch(r"[0-9]{1,30}",expected_user_id):
        raise ExtraSocialBlocked("X account ID must be explicitly verified")
    _,who,_=requester("https://api.x.com/2/users/me",token)
    if str((who.get("data") or {}).get("id") or "")!=expected_user_id:
        raise ExtraSocialBlocked("X token does not belong to approved account")
    data=jpg.read_bytes()
    _,result,_=requester("https://api.x.com/2/media/upload/initialize",token,
                        method="POST",payload={"total_bytes":len(data),
                                               "media_type":"image/jpeg",
                                               "media_category":"tweet_image"})
    media=(result.get("data") or result)
    mid=str(media.get("id") or media.get("media_id") or "")
    if not re.fullmatch("[0-9]{1,30}",mid):raise ExtraSocialBlocked("X media upload ID missing")
    # v2 chunked upload; one small JPEG fits a single segment.
    boundary="----TrustFolio"+uuid.uuid4().hex
    body=("--"+boundary+"\r\nContent-Disposition: form-data; name=\"media\"; filename=\"trustfolio.jpg\"\r\n"
          "Content-Type: image/jpeg\r\n\r\n").encode()+data+("\r\n--"+boundary+"--\r\n").encode()
    requester("https://api.x.com/2/media/upload/"+mid+"/append",token,method="POST",raw=body,
              content_type="multipart/form-data; boundary="+boundary)
    requester("https://api.x.com/2/media/upload/"+mid+"/finalize",token,method="POST",payload={})
    _,result,_=requester("https://api.x.com/2/tweets",token,method="POST",
                         payload={"text":x_post_text(post),"media":{"media_ids":[mid]}})
    tweet=str((result.get("data") or {}).get("id") or "")
    if not re.fullmatch("[0-9]{1,30}",tweet):
        raise ExtraSocialBlocked("X post response lacks post ID")
    return tweet

def publish_network(network,post,jpg,env,*,gh_token):
    if network not in NETWORKS:raise ExtraSocialBlocked("Unknown network")
    flag=env.get("TF_LINKEDIN_DIRECT_PUBLISH_ENABLED") if network=="linkedin" else env.get("TF_X_DIRECT_PUBLISH_ENABLED")
    if flag!="true":
        print("EXTRA_SOCIAL_NOT_ENABLED="+network)
        return "disabled"
    if env.get("GITHUB_REPOSITORY")!=REPO:
        raise ExtraSocialBlocked("Wrong GitHub repo")
    if network=="linkedin":
        access=env.get("TF_LINKEDIN_ACCESS_TOKEN") or ""
        owner=env.get("TF_LINKEDIN_AUTHOR_URN") or ""
        if len(access)<20 or not owner:raise ExtraSocialBlocked("LinkedIn OAuth token/author not connected")
    else:
        access=env.get("TF_X_USER_ACCESS_TOKEN") or ""
        owner=env.get("TF_X_USER_ID") or ""
        if len(access)<20 or not owner:raise ExtraSocialBlocked("X user OAuth token/account not connected")
        if env.get("TF_X_PAID_API_APPROVED")!="true":
            raise ExtraSocialBlocked("Paid X API spending not explicitly approved")
    # Reserve BEFORE any external request with side effects.
    path=reserve_slot(gh_token,network,post)
    if path is None:return "duplicate"
    if network=="linkedin":
        ident=linkedin_image_post(post,jpg,access,owner,env.get("TF_LINKEDIN_VERSION") or "202608")
    else:
        ident=x_image_post(post,jpg,access,owner)
    complete_slot(gh_token,path,network,post,ident)
    print("EXTRA_SOCIAL_API_ACCEPTED_PUBLISHED="+network+":"+post["mode"])
    return "published"

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--folder",default="source-social-ad")
    parser.add_argument("--network",choices=NETWORKS,required=True)
    parser.add_argument("--live",action="store_true")
    args=parser.parse_args()
    token=os.getenv("GITHUB_TOKEN") or ""
    post,jpg,url=validate_source(args.folder,gh_token=token if args.live else None,
                                 verify_live=args.live)
    print("EXTRA_SOCIAL_SOURCE_QA=PASS")
    print("EXTRA_SOCIAL_MODE="+post["mode"])
    print("EXTRA_SOCIAL_CAMPAIGN_ID="+post["campaign_id"])
    if not args.live:
        print("EXTRA_SOCIAL_DRY_RUN=YES")
        if args.network=="linkedin":
            print("LINKEDIN_CAPTION_PREVIEW_START")
            print(linkedin_post_text(post))
            print("LINKEDIN_CAPTION_PREVIEW_END")
        if args.network=="x":print("X_TEXT_LENGTH="+str(len(x_post_text(post))))
        return
    if os.getenv("GITHUB_EVENT_NAME")!="workflow_run":
        raise ExtraSocialBlocked("Real crossposting permitted only on completed scheduled Meta workflow")
    if not token:raise ExtraSocialBlocked("GitHub reservation token missing")
    publish_network(args.network,post,jpg,os.environ,gh_token=token)

if __name__=="__main__":
    try:main()
    except (ExtraSocialBlocked,PublishingBlocked,PriceAuditBlocked) as exc:
        print("EXTRA_SOCIAL_BLOCKED="+str(exc))
        raise SystemExit(1)
