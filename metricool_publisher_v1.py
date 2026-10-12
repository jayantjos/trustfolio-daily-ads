#!/usr/bin/env python3
"""Safe, one-post-at-a-time Metricool publisher for TrustFolio.

Default behavior is verification only. A live post requires both --schedule-one
and --qa-approved. This script never publishes a batch.
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, tempfile
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from PIL import Image, UnidentifiedImageError

BASE = Path.home() / "new_scraper"
DEFAULT_MANIFEST = BASE / "ads" / "social_post_manifest_v1.json"
DEFAULT_STATE = BASE / "ads" / "metricool_publish_state_v1.json"
DEFAULT_QA = BASE / "ads" / "metricool_media_qa_v1.json"
API = "https://app.metricool.com/api"
TIMEZONE = os.getenv("TRUSTFOLIO_POST_TIMEZONE", "Asia/Kolkata")
MAX_IMAGE_BYTES = 20 * 1024 * 1024

class PublishError(RuntimeError):
    pass

def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PublishError(f"Required JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PublishError(f"Invalid JSON in {path}: {exc}") from exc

def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def find_ad(manifest, ad_id):
    matches = [a for a in manifest.get("ads", []) if a.get("ad_id") == ad_id]
    if len(matches) != 1:
        raise PublishError(f"Expected exactly one ad_id={ad_id!r}; found {len(matches)}.")
    return matches[0]

def fetch_public_image(url):
    if not url.startswith("https://"):
        raise PublishError("Media URL must use HTTPS.")
    req = Request(url, headers={"User-Agent": "TrustFolio-Media-QA/1.0"})
    try:
        with urlopen(req, timeout=25) as response:
            status = getattr(response, "status", 200)
            content_type = response.headers.get_content_type()
            final_url = response.geturl()
            body = response.read(MAX_IMAGE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise PublishError(f"Public media fetch failed: {type(exc).__name__}: {exc}") from exc
    if status < 200 or status >= 300:
        raise PublishError(f"Public media returned HTTP {status}.")
    if not final_url.startswith("https://"):
        raise PublishError("Media redirected away from HTTPS.")
    if len(body) > MAX_IMAGE_BYTES:
        raise PublishError(f"Image exceeds {MAX_IMAGE_BYTES} bytes.")
    if len(body) < 10 * 1024:
        raise PublishError(f"Image is suspiciously small ({len(body)} bytes).")
    if not content_type.startswith("image/"):
        raise PublishError(f"Expected image content, received {content_type!r}.")
    try:
        with Image.open(BytesIO(body)) as im:
            fmt, width, height = im.format, *im.size
            im.verify()
        with Image.open(BytesIO(body)) as im2:
            im2.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise PublishError(f"Image bytes could not be decoded: {exc}") from exc
    if width < 600 or height < 600:
        raise PublishError(f"Image dimensions too small: {width}x{height}.")
    return body, {
        "http_status": status, "content_type": content_type,
        "final_url": final_url, "format": fmt, "width": width,
        "height": height, "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest()
    }

def metricool_request(method, path, params, body=None):
    token = os.getenv("METRICOOL_API_TOKEN", "").strip()
    if not token:
        raise PublishError("METRICOOL_API_TOKEN is missing from server environment.")
    headers = {"X-Mc-Auth": token, "Accept": "application/json",
               "User-Agent": "TrustFolio-Metricool-Publisher/1.0"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    url = API + path + "?" + urlencode(params)
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = response.status
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        if exc.code in (401, 403):
            raise PublishError(f"Metricool auth/permission failed (HTTP {exc.code}); check token, userId, blogId and plan. {detail}") from exc
        raise PublishError(f"Metricool API returned HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise PublishError(f"Metricool API request failed: {type(exc).__name__}: {exc}") from exc
    try:
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return {"raw_response": raw[:1200]}

def find_media_id(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in {"mediaid", "media_id"} and item not in (None, ""):
                return str(item)
        for item in value.values():
            found = find_media_id(item)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = find_media_id(item)
            if found:
                return found
    return None

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--qa-report", type=Path, default=DEFAULT_QA)
    parser.add_argument("--ad-id", required=True)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--schedule-one", action="store_true")
    parser.add_argument("--qa-approved", action="store_true",
                        help="One-time confirmation that this exact image was visually inspected.")
    parser.add_argument("--publish-at", help="Future local time, e.g. 2026-10-13T10:30.")
    args = parser.parse_args()

    if args.schedule_one and not args.qa_approved:
        raise PublishError("Publishing blocked: run --verify-only, visually inspect that exact image, then pass --qa-approved.")
    if args.verify_only and args.schedule_one:
        raise PublishError("Choose either --verify-only or --schedule-one, not both.")
    if not args.verify_only and not args.schedule_one:
        args.verify_only = True

    ad = find_ad(read_json(args.manifest), args.ad_id)
    media = (ad.get("media") or {}).get("feed_image") or {}
    media_url = str(media.get("url") or "").strip()
    if not media_url:
        raise PublishError("Selected ad has no feed_image.url.")
    posts = ad.get("posts") or {}
    instagram = posts.get("instagram") or {}
    caption = str(instagram.get("caption") or "").strip()
    hashtags = instagram.get("hashtags") or []
    caption = (caption + "\n\n" + " ".join(str(t) for t in hashtags)).strip()
    if not caption:
        raise PublishError("Instagram caption is empty.")
    landing_url = str(ad.get("landing_url") or "").strip()
    if landing_url and not landing_url.startswith("https://"):
        raise PublishError("Landing URL must use HTTPS.")

    _, img = fetch_public_image(media_url)
    report = {
        "version": 1, "checked_at": datetime.now(ZoneInfo(TIMEZONE)).isoformat(),
        "ad_id": args.ad_id, "category": ad.get("category"),
        "headline": ad.get("headline"), "media_url": media_url,
        "image": img, "caption_characters": len(caption),
        "caption_sha256": hashlib.sha256(caption.encode("utf-8")).hexdigest(),
        "landing_url": landing_url,
        "visual_review": "PENDING_HUMAN_VISUAL_INSPECTION",
        "publish_attempted": False
    }
    atomic_json(args.qa_report, report)
    print("PUBLIC MEDIA QA: PASS")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"QA report saved: {args.qa_report}")
    if args.verify_only:
        print("VERIFY ONLY: no Metricool API calls and no post scheduled.")
        return 0

    state = read_json(args.state) if args.state.exists() else {"version": 1, "scheduled": []}
    scheduled = state.setdefault("scheduled", [])
    if any(x.get("ad_id") == args.ad_id and x.get("network") == "instagram" for x in scheduled):
        raise PublishError(f"Duplicate guard: {args.ad_id} is already recorded as scheduled for Instagram.")

    user_id = os.getenv("METRICOOL_USER_ID", "").strip()
    blog_id = os.getenv("METRICOOL_BLOG_ID", "").strip()
    if not user_id or not blog_id:
        raise PublishError("METRICOOL_USER_ID and METRICOOL_BLOG_ID must be set in server environment.")
    if os.getenv("METRICOOL_INSTAGRAM_CONNECTED", "").strip().lower() != "true":
        raise PublishError("Publishing blocked: set METRICOOL_INSTAGRAM_CONNECTED=true only after confirming Instagram is connected to this exact Metricool brand.")
    if args.publish_at:
        try:
            publish_dt = datetime.fromisoformat(args.publish_at)
        except ValueError as exc:
            raise PublishError("--publish-at must look like 2026-10-13T10:30.") from exc
        if publish_dt.tzinfo is not None:
            publish_dt = publish_dt.astimezone(ZoneInfo(TIMEZONE)).replace(tzinfo=None)
    else:
        publish_dt = datetime.now(ZoneInfo(TIMEZONE)).replace(tzinfo=None) + timedelta(minutes=20)
    if publish_dt <= datetime.now(ZoneInfo(TIMEZONE)).replace(tzinfo=None) + timedelta(minutes=2):
        raise PublishError("Publish time must be at least 2 minutes in the future.")

    normalized = metricool_request("GET", "/actions/normalize/image/url",
        {"url": media_url, "userId": user_id, "blogId": blog_id})
    media_id = find_media_id(normalized)
    if not media_id:
        raise PublishError("Image normalization did not return mediaId; nothing was scheduled. Inspect response schema before changing this script.")

    body = {
        "publicationDate": {"dateTime": publish_dt.isoformat(timespec="minutes"), "timezone": TIMEZONE},
        "text": caption,
        "providers": [{"network": "instagram"}],
        "autoPublish": True, "draft": False, "shortener": False,
        "saveExternalMediaFiles": True,
        "media": {"mediaId": media_id},
        "instagramData": {"type": "POST"}
    }
    response = metricool_request("POST", "/v2/scheduler/posts",
        {"blogId": blog_id, "userId": user_id}, body)
    record = {
        "ad_id": args.ad_id, "network": "instagram",
        "scheduled_at": publish_dt.isoformat(), "media_url": media_url,
        "media_sha256": img["sha256"], "caption_sha256": report["caption_sha256"],
        "metricool_response": response,
        "recorded_at": datetime.now(ZoneInfo(TIMEZONE)).isoformat()
    }
    scheduled.append(record)
    state["updated_at"] = datetime.now(ZoneInfo(TIMEZONE)).isoformat()
    atomic_json(args.state, state)
    report["visual_review"] = "HUMAN_CONFIRMED_BY_CLI_FLAG"
    report["publish_attempted"] = True
    report["scheduled_at"] = publish_dt.isoformat()
    report["metricool_response"] = response
    atomic_json(args.qa_report, report)
    print("ONE POST SCHEDULED. No batch or other ad was submitted.")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except PublishError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        sys.exit(2)
