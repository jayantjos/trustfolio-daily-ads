"""Read-only Buffer delivery reconciliation for TrustFolio LinkedIn.

Never create, reschedule, or retry a post here. Mark sent only with provider
status and timestamp for the exact immutable locked Buffer post ID.
"""
import argparse,base64,json,os,re
from datetime import datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from automation.buffer_free_crosspost_v1 import graphql,BufferBlocked
from automation.linkedin_x_crosspost_v1 import _github,LEDGER, get_ledger

IST=ZoneInfo("Asia/Kolkata")
MODES=("budget","brand_budget","comparison")
POST_QUERY="""query VerifyTrustFolioPost($input: PostInput!) {
  post(input: $input) {
    id status sentAt externalLink channelId
  }
}"""

def inspect_provider(token,post_id,channel_id,*,request=graphql):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}",post_id):
        raise BufferBlocked("Invalid recorded Buffer ID")
    data=request(token,POST_QUERY,{"input":{"id":post_id}}).get("post") or {}
    if str(data.get("id"))!=post_id or str(data.get("channelId"))!=channel_id:
        raise BufferBlocked("Buffer post identity/channel mismatch")
    status=str(data.get("status") or "").lower()
    if status=="sent":
        sent_at=str(data.get("sentAt") or "")
        if not sent_at:
            raise BufferBlocked("Buffer sent without publication timestamp")
        link=str(data.get("externalLink") or "")
        if link:
            url=urlsplit(link)
            if url.scheme!="https" or url.hostname not in ("linkedin.com","www.linkedin.com"):
                raise BufferBlocked("Unexpected external LinkedIn publication URL")
        return {"status":"sent","sent_at":sent_at,"external_link":link}
    if status in ("scheduled","buffer","draft","error","failed"):
        return {"status":status}
    raise BufferBlocked("Unknown provider delivery status")

def reconcile(mode,day,token,github_token,channel_id,*,request=graphql,github=_github):
    if mode not in MODES:
        raise BufferBlocked("Unknown LinkedIn mode")
    path=f"extra-social-ledger/{day}/linkedin-mode-{mode}.json"
    entry=get_ledger(github_token,LEDGER,path)
    if entry is None:
        print("LINKEDIN_NO_BUFFER_RECORD="+mode)
        return "absent"
    if entry.get("status")=="buffer_confirmed_sent":
        print("LINKEDIN_ALREADY_CONFIRMED="+mode)
        return "sent"
    if entry.get("status")!="buffer_api_accepted_scheduled":
        print("LINKEDIN_LOCK_NOT_RECONCILABLE="+str(entry.get("status")))
        return "locked"
    ident=str(entry.get("buffer_post_id") or "")
    result=inspect_provider(token,ident,channel_id,request=request)
    print("BUFFER_PROVIDER_STATUS="+mode+":"+result["status"])
    if result["status"]!="sent":
        return result["status"]
    file=github(github_token,"contents/"+path+"?ref="+LEDGER)
    current=json.loads(base64.b64decode(file["content"]))
    if (current.get("status")!="buffer_api_accepted_scheduled"
       or current.get("buffer_post_id")!=ident
       or current.get("campaign_id")!=entry.get("campaign_id")):
        raise BufferBlocked("LinkedIn ledger updated during reconciliation")
    current.update({
        "status":"buffer_confirmed_sent",
        "buffer_provider_status":"sent",
        "buffer_sent_at":result["sent_at"],
        "external_post_url":result["external_link"],
        "verified_at":datetime.now(IST).isoformat()
    })
    github(github_token,"contents/"+path,method="PUT",
      data={"branch":LEDGER,"sha":file["sha"],
            "content":base64.b64encode(json.dumps(current,sort_keys=True).encode()).decode(),
            "message":"Confirm LinkedIn Buffer sent "+mode})
    print("LINKEDIN_BUFFER_CONFIRMED_SENT="+mode+":"+ident)
    return "sent"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",required=True,choices=MODES)
    args=p.parse_args()
    day=datetime.now(IST).date().isoformat()
    key=os.getenv("TF_BUFFER_API_KEY") or ""
    gh=os.getenv("GITHUB_TOKEN") or ""
    channel=os.getenv("TF_BUFFER_LINKEDIN_CHANNEL_ID") or ""
    if len(key)<20 or not gh or not channel:
        raise SystemExit("Missing Buffer/GitHub read credentials")
    reconcile(args.mode,day,key,gh,channel)

if __name__=="__main__":main()
