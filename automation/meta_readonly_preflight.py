"""Read-only first-party Meta connection test; NEVER publishes media.

Uses the owner's official Meta Page access token from GitHub Actions Secrets.
Reports only verified Page ID, Instagram handle and rolling 24-hour quota.
Does not print access tokens, personally identifying account metadata or posts.
"""
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from automation.meta_graph_publish_v1 import (
    EXPECTED_PAGE_ID, PublishingBlocked,
    confirm_page_identity, check_instagram_quota
)


def run_read_only(environ=None):
    environ = environ if environ is not None else os.environ
    token = environ.get("TF_META_PAGE_ACCESS_TOKEN") or ""
    if len(token) < 20:
        raise PublishingBlocked("TF_META_PAGE_ACCESS_TOKEN secret missing; authorize in Meta Developer dashboard")
    page_id = environ.get("TF_META_PAGE_ID") or EXPECTED_PAGE_ID
    if page_id != EXPECTED_PAGE_ID:
        raise PublishingBlocked("Configured Page does not match previously verified TrustFolio Page")
    cfg = {
        "version":environ.get("TF_META_GRAPH_VERSION") or "v25.0",
        "page_id":page_id,
        "page_token":token,
    }
    igid = confirm_page_identity(cfg)
    usage=check_instagram_quota(cfg,igid)
    return {"facebook_page_verified":page_id,"instagram_username_verified":"trustfolio3",
            "instagram_user_id":igid, "instagram_quota":usage,
            "publication_attempted":False}


def main():
    result=run_read_only()
    print("META_TRUSTFOLIO_FACEBOOK_PAGE_VERIFIED="+result["facebook_page_verified"])
    print("META_TRUSTFOLIO_INSTAGRAM_VERIFIED=@"+result["instagram_username_verified"])
    print("META_IG_CURRENT_QUOTA_USAGE="+str(result["instagram_quota"]["quota_usage"]))
    print("META_IG_CURRENT_QUOTA_TOTAL="+str(result["instagram_quota"]["quota_total"]))
    print("META_POSTS_CREATED=0")


if __name__ == "__main__":
    main()
