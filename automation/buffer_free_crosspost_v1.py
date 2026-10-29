"""Optional zero-subscription Buffer Free scheduler for TrustFolio LinkedIn + X.

Connect only the intended LinkedIn and X channels in Buffer Free. Reuse the
exact original Meta-approved 1080x1350 image, fresh five-product QA and link.
No direct X API account or usage billing. No network calls without opt-in.
"""
import argparse
import base64
from datetime import datetime,timedelta,timezone
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from automation.linkedin_x_crosspost_v1 import (
    NETWORKS,REPO,LEDGER,ExtraSocialBlocked,validate_source,
    reserve_slot,get_ledger,ledger_path,x_post_text,linkedin_post_text,
)
from automation.meta_graph_publish_v1 import _github
from zoneinfo import ZoneInfo

BUFFER_GRAPHQL="https://api.buffer.com"
IST=ZoneInfo("Asia/Kolkata")

class BufferBlocked(ExtraSocialBlocked):
    pass

def graphql(token,query,variables=None,*,opener=urlopen):
    if not isinstance(token,str) or len(token)<20:
        raise BufferBlocked("Connect Buffer Free API key through GitHub Actions secret")
    req=Request(BUFFER_GRAPHQL,method="POST",
        data=json.dumps({"query":query,"variables":variables or {}}).encode("utf8"),
        headers={"Authorization":"Bearer "+token,
                 "Content-Type":"application/json",
                 "Accept":"application/json",
                 "User-Agent":"TrustFolioFreeCrossposting/1.0"})
    try:
        with opener(req,timeout=35) as res:
            body=json.loads(res.read(600_000))
    except HTTPError as err:
        raise BufferBlocked("Buffer HTTP "+str(err.code)) from None
    except (URLError,TimeoutError,ValueError,OSError):
        raise BufferBlocked("Buffer unavailable or returned invalid JSON") from None
    if not isinstance(body,dict):
        raise BufferBlocked("Buffer JSON is not an object")
    if body.get("errors"):
        # No free-form server-supplied text in CI logs.
        raise BufferBlocked("Buffer GraphQL rejected the operation")
    return body.get("data") or {}

ACCOUNT_QUERY="query { account { organizations { id name } } }"
def channel_query(org_id):
    # Organization ID is API-provided but allow no GraphQL injection.
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}",org_id):
        raise BufferBlocked("Invalid Buffer organization ID")
    return "query { channels(input: { organizationId: "+json.dumps(org_id)+" }) { id name service } }"

def verify_buffer_channel(token,network,expected_id,*,graphql_request=graphql):
    if network not in NETWORKS:
        raise BufferBlocked("Unsupported social channel")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}",str(expected_id or "")):
        raise BufferBlocked("Missing pinned Buffer channel ID")
    record=graphql_request(token,ACCOUNT_QUERY)
    organizations=(record.get("account") or {}).get("organizations") or []
    if not 1<=len(organizations)<=25:
        raise BufferBlocked("Buffer account has no readable organizations")
    matching=[]
    for org in organizations:
        data=graphql_request(token,channel_query(str(org.get("id") or "")))
        for channel in data.get("channels") or []:
            if str(channel.get("id"))==expected_id:
                matching.append(channel)
    if len(matching)!=1:
        raise BufferBlocked("Authorized Buffer channel not uniquely connected")
    service=str(matching[0].get("service") or "").casefold()
    allowed={"linkedin":("linkedin",),"x":("twitter","x")}
    if service not in allowed[network]:
        raise BufferBlocked("Buffer channel is not the expected social platform")
    return matching[0]

CREATE_MUTATION="""mutation TrustFolioCreate($input: CreatePostInput!) {
  createPost(input: $input) {
    __typename
    ... on PostActionSuccess {
      post { id text dueAt }
    }
    ... on MutationError { message }
  }
}"""

def submit_to_buffer(token,post,network,channel_id,media_url,*,now=None,
                     graphql_request=graphql):
    if network not in NETWORKS:
        raise BufferBlocked("Unknown network")
    if media_url!="https://media.trustfolio.in/trustfolio-auto/"+post["campaign_id"]+".jpg":
        raise BufferBlocked("Media URL does not match QA campaign image")
    verify_buffer_channel(token,network,channel_id,graphql_request=graphql_request)
    caption=linkedin_post_text(post) if network=="linkedin" else x_post_text(post)
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise BufferBlocked("Buffer schedule must use UTC aware time")
    due=(now.astimezone(timezone.utc)+timedelta(minutes=5)).isoformat(timespec="milliseconds").replace("+00:00","Z")
    payload={"channelId":channel_id,"text":caption,
             "schedulingType":"automatic","mode":"customScheduled",
             "dueAt":due,"assets":[{"image":{"url":media_url}}]}
    result=graphql_request(token,CREATE_MUTATION,{"input":payload}).get("createPost") or {}
    if result.get("__typename")!="PostActionSuccess":
        raise BufferBlocked("Buffer rejected createPost, check channel permissions/free queue limit")
    posted=result.get("post") or {}
    post_id=str(posted.get("id") or "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}",post_id):
        raise BufferBlocked("Buffer did not return a scheduled post ID")
    if posted.get("text")!=caption:
        raise BufferBlocked("Buffer response caption mismatch")
    return {"id":post_id,"due_at":due,"network":network}

def complete_scheduled(token,path,post,result):
    """Store *scheduled*, never falsely claim actual network publication."""
    entry=_github(token,"contents/"+path+"?ref="+LEDGER)
    value=json.loads(base64.b64decode(entry["content"]).decode("utf8"))
    if value.get("status")!="reserved" or value.get("campaign_id")!=post["campaign_id"]:
        raise BufferBlocked("Buffer schedule reservation changed")
    value.update({"status":"buffer_api_accepted_scheduled",
                  "buffer_post_id":result["id"],
                  "due_at_utc":result["due_at"],
                  "recorded_at":datetime.now(IST).isoformat()})
    encoded=base64.b64encode(json.dumps(value).encode("utf8")).decode()
    _github(token,"contents/"+path,method="PUT",
            data={"branch":LEDGER,"sha":entry["sha"],"content":encoded,
                  "message":"Buffer Free scheduled "+result["network"]+" "+post["mode"]})

def schedule_if_enabled(network,post,media_url,env,*,gh_token,
                        do_submit=submit_to_buffer,reserve=reserve_slot,
                        complete=complete_scheduled):
    if network not in NETWORKS:raise BufferBlocked("Unknown network")
    if env.get("TF_BUFFER_FREE_PUBLISH_ENABLED")!="true":
        print("BUFFER_FREE_NOT_ENABLED="+network)
        return "disabled"
    if env.get("GITHUB_REPOSITORY")!=REPO:
        raise BufferBlocked("Wrong GitHub repository")
    token=env.get("TF_BUFFER_API_KEY") or ""
    channel=env.get("TF_BUFFER_LINKEDIN_CHANNEL_ID" if network=="linkedin"
                    else "TF_BUFFER_X_CHANNEL_ID") or ""
    if len(token)<20 or not channel:
        raise BufferBlocked("Buffer API key/channel not configured")
    # Direct-API and Buffer integrations share the same per-date/network/mode
    # reservation namespace, so enabling both can never create duplicates.
    lock=reserve(gh_token,network,post)
    if lock is None:return "duplicate"
    result=do_submit(token,post,network,channel,media_url)
    complete(gh_token,lock,post,result)
    print("BUFFER_FREE_SCHEDULED="+network+":"+post["mode"])
    return "scheduled"

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--folder",default="source-social-ad")
    parser.add_argument("--network",required=True,choices=NETWORKS)
    parser.add_argument("--live",action="store_true")
    args=parser.parse_args()
    trusted_catchup=(
        args.network=="linkedin"
        and os.getenv("TF_LINKEDIN_CATCHUP_APPROVED")=="true"
        and os.getenv("GITHUB_WORKFLOW")=="TrustFolio LinkedIn 3-mode independent same-day catch-up"
        and os.getenv("GITHUB_REF")=="refs/heads/main"
        and os.getenv("GITHUB_REPOSITORY")==REPO
        and os.getenv("GITHUB_EVENT_NAME") in ("push","schedule","workflow_dispatch")
    )
    if args.live and not (
        os.getenv("GITHUB_EVENT_NAME")=="workflow_run" or trusted_catchup or (
            args.network=="linkedin"
            and os.getenv("GITHUB_EVENT_NAME")=="workflow_dispatch"
            and os.getenv("TF_MANUAL_LINKEDIN_RECOVERY_APPROVED")=="true"
        )
    ):
        raise BufferBlocked("Live Buffer requires automatic Meta event or explicit LinkedIn recovery approval")
    token=os.getenv("GITHUB_TOKEN") or ""
    post,jpg,url=validate_source(args.folder,gh_token=token if args.live else None,
                                  verify_live=args.live)
    print("BUFFER_FREE_SOURCE_QA=PASS")
    print("BUFFER_FREE_CAMPAIGN_ID="+post["campaign_id"])
    print("BUFFER_FREE_TARGET="+args.network)
    if not args.live:
        print("BUFFER_FREE_DRY_RUN=YES")
        if args.network=="linkedin":
            print("LINKEDIN_CAPTION_PREVIEW_START")
            print(linkedin_post_text(post))
            print("LINKEDIN_CAPTION_PREVIEW_END")
        return
    if not token:raise BufferBlocked("Missing GitHub lock token")
    schedule_if_enabled(args.network,post,url,os.environ,gh_token=token)

if __name__=="__main__":
    try:main()
    except (BufferBlocked,ExtraSocialBlocked) as err:
        print("BUFFER_FREE_BLOCKED="+str(err))
        raise SystemExit(1)
