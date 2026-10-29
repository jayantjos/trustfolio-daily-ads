"""Published Meta campaign history used to prevent repeating category + budget.

Read only GitHub's existing audited publication ledger. Historical records from
older publisher versions are recovered by matching their deterministic SHA IDs
to the original daily rotation. New publication records include explicit fields.
All history reads are authenticated; a network/ledger error blocks planning
instead of silently losing deduplication protection.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from automation.auto_campaign_v1 import MODES, campaign_id, rotation_candidates

REPOSITORY = "jayantjos/trustfolio-daily-ads"
LEDGER_BRANCH = "trustfolio-meta-publishing-ledger"
ORIGIN = "https://api.github.com/repos/" + REPOSITORY


class HistoryUnavailable(ValueError):
    pass


def _github_read(path, token, *, opener=urlopen):
    if len(token or "") < 20:
        raise HistoryUnavailable("Missing GitHub read token for budget history")
    url = ORIGIN + "/" + path
    req = Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "User-Agent": "TrustFolioPublishingHistory/1.0",
    })
    try:
        with opener(req, timeout=30) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        raise HistoryUnavailable("Cannot read publication history (" + type(exc).__name__ + ")") from None


def _historical_identity(record, day, policy, path):
    """Determine category/budget from explicit metadata, or old SHA campaign ID."""
    category = record.get("category")
    budget = record.get("budget_inr")
    if isinstance(category, str) and category and type(budget) is int and budget > 0:
        return category, budget
    key = record.get("campaign_id") or ""
    if not re.fullmatch(r"tfauto-[0-9a-f]{18}", str(key)):
        return None
    mode = record.get("mode")
    modes = [mode] if mode in MODES else MODES
    if mode not in MODES:
        # Old ledgers were named by campaign ID instead of mode.
        mode_from_name = re.search(r"-mode-(budget|brand_budget|comparison)\.json$", path)
        if mode_from_name:
            modes = [mode_from_name.group(1)]
    for target_mode in modes:
        candidates = []
        for slot in (0, 1):
            candidates.extend(rotation_candidates(target_mode, policy, day, slot=slot) or [])
        candidates.extend((policy.get("campaigns") or {}).get(target_mode) or [])
        for item in candidates:
            category = str(item["category"])
            budget = int(item["budget"])
            brand = str(item.get("brand") or "") if target_mode == "brand_budget" else ""
            if campaign_id(day, target_mode, category, budget, brand) == key:
                return category, budget
    return None


def used_budgets_from_records(records, policy, today, lookback_days=45):
    """Pure transform: includes only successful posts, across all modes/networks."""
    today = date.fromisoformat(str(today))
    cutoff = today - timedelta(days=lookback_days)
    used = {}
    unknown = 0
    for path, record in records:
        try:
            day = date.fromisoformat(path.split("/")[1])
        except (ValueError, IndexError):
            continue
        if day < cutoff or day > today or record.get("status") != "api_accepted_published":
            continue
        identity = _historical_identity(record, day, policy, path)
        if identity is None:
            unknown += 1
            continue
        used.setdefault(identity, set()).add(day.isoformat())
    return {
        "used": [
            {"category": cat, "budget": bud, "dates": sorted(days)}
            for (cat, bud), days in sorted(used.items())
        ],
        "unresolved_legacy_records": unknown,
        "lookback_days": lookback_days,
        "generated_for": today.isoformat(),
    }


def fetch_successful_records(token, today, *, lookback_days=45, getter=_github_read):
    today = date.fromisoformat(str(today))
    cutoff = today - timedelta(days=lookback_days)
    tree = getter("git/trees/" + LEDGER_BRANCH + "?recursive=1", token)
    if tree.get("truncated") or not isinstance(tree.get("tree"), list):
        raise HistoryUnavailable("Publication history Git tree incomplete")
    eligible = []
    for entry in tree["tree"]:
        path = entry.get("path") or ""
        if entry.get("type") != "blob" or not re.fullmatch(
            r"meta-publication-ledger/\d{4}-\d{2}-\d{2}/(facebook|instagram)-[a-zA-Z0-9_-]+\.json", path
        ):
            continue
        day = date.fromisoformat(path.split("/")[1])
        if cutoff <= day <= today:
            blob = entry.get("sha") or ""
            if not re.fullmatch(r"[0-9a-f]{40}", blob):
                raise HistoryUnavailable("Publication blob ID invalid")
            eligible.append((path, blob))
    if len(eligible) > 600:
        raise HistoryUnavailable("Unusually large publication history; inspect before scheduling")

    def load(entry):
        path, blob = entry
        result = getter("git/blobs/" + blob, token)
        if result.get("encoding") != "base64":
            raise HistoryUnavailable("Publication history blob is not base64")
        try:
            raw = base64.b64decode(result["content"], validate=False)
            record = json.loads(raw.decode("utf8"))
            if not isinstance(record, dict):
                raise ValueError("not an object")
        except (KeyError, ValueError, UnicodeError, TypeError):
            raise HistoryUnavailable("Unreadable publication history record") from None
        return path, record

    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(load, eligible))


def main():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--policy", default="automation/campaigns.json")
    parser.add_argument("--day", default=datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat())
    parser.add_argument("--lookback-days", type=int, default=45)
    args = parser.parse_args()
    if args.lookback_days < 1 or args.lookback_days > 90:
        raise HistoryUnavailable("Lookback must be 1 to 90 days")
    policy = json.loads(Path(args.policy).read_text("utf8"))
    records = fetch_successful_records(
        os.environ.get("GH_TOKEN") or "", args.day, lookback_days=args.lookback_days
    )
    result = used_budgets_from_records(records, policy, args.day, lookback_days=args.lookback_days)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print("PUBLISHED_BUDGET_PAIRS_EXCLUDED=" + str(len(result["used"])))
    print("UNRESOLVED_LEGACY_PUBLISHED_RECORDS=" + str(result["unresolved_legacy_records"]))


if __name__ == "__main__":
    main()
