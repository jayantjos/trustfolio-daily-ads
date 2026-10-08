#!/usr/bin/env python3
"""
Publish TrustFolio metadata/manifests to GitHub.

Generated media files are intentionally NOT copied into GitHub.
They are served from the public media host at https://media.trustfolio.in.
This prevents the daily Git checkout from consuming unnecessary disk space.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

NEW_SCRAPER = Path.home() / "new_scraper"
GIT_REPO = Path.home() / "daily_ads_git"
ADS = NEW_SCRAPER / "ads"

FILES = [
    "daily_ads_20_categories_v8.json",
    "creative_ad_manifest_v1.json",
    "creative_generation_manifest_v1.json",
    "social_post_manifest_v1.json",
    "public_media_manifest_v1.json",
]


def run(cmd, cwd=None, check=True):
    print("$", " ".join(str(x) for x in cmd))
    p = subprocess.run(
        [str(x) for x in cmd],
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
    )
    if p.stdout:
        print(p.stdout.rstrip())
    if p.returncode != 0:
        if p.stderr:
            print(p.stderr.rstrip())
        if check:
            raise SystemExit(p.returncode)
    return p


def main():
    if not GIT_REPO.exists():
        raise SystemExit(f"Git repository not found: {GIT_REPO}")

    print("=" * 88)
    print("TRUSTFOLIO GITHUB METADATA BRIDGE V2")
    print("=" * 88)

    run(["git", "pull", "--ff-only", "origin", "main"], cwd=GIT_REPO)

    # Remove historical binary creatives from the Git working tree.
    tracked_media = run(
        ["git", "ls-files", "generated_creatives"],
        cwd=GIT_REPO,
    ).stdout.strip()

    if tracked_media:
        run(["git", "rm", "-r", "generated_creatives"], cwd=GIT_REPO)

    dest = GIT_REPO / "manifests"
    dest.mkdir(parents=True, exist_ok=True)

    published = []
    missing = []

    for name in FILES:
        src = ADS / name
        if not src.exists():
            missing.append(name)
            continue

        target = dest / name
        target.write_bytes(src.read_bytes())
        published.append(name)

    if missing:
        raise SystemExit(
            "Missing required manifests: " + ", ".join(missing)
        )

    manifest = {
        "version": "2.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "repository": "jayantjos/trustfolio-daily-ads",
        "branch": "main",
        "purpose": "TrustFolio daily automation metadata bridge",
        "media_host": "https://media.trustfolio.in",
        "media_files_in_git": False,
        "published_files": published,
    }

    (GIT_REPO / "creative_publish_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    run(
        ["git", "add", "manifests", "creative_publish_manifest.json"],
        cwd=GIT_REPO,
    )

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(GIT_REPO),
        text=True,
        capture_output=True,
        check=False,
    )

    if not status.stdout.strip():
        print("Nothing new to commit.")
        return

    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    run(
        ["git", "commit", "-m", f"Publish TrustFolio manifests {stamp}"],
        cwd=GIT_REPO,
    )
    run(["git", "push", "origin", "main"], cwd=GIT_REPO)

    print()
    print("=" * 88)
    print("PUBLISH COMPLETE")
    print("=" * 88)
    print("Manifests pushed:", len(published))
    print("Media in GitHub :", "NO")
    print("Media host      :", "https://media.trustfolio.in")
    print("=" * 88)


if __name__ == "__main__":
    main()
