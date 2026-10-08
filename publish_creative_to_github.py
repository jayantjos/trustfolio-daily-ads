#!/usr/bin/env python3
"""
Copy generated TrustFolio creatives from ~/new_scraper into the dedicated
GitHub bridge repo ~/daily_ads_git and push them to origin/main.

This script does NOT modify the TrustFolio Node backend.
It is intentionally limited to generated creative files and metadata.
"""

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

NEW_SCRAPER = Path.home() / "new_scraper"
GIT_REPO = Path.home() / "daily_ads_git"
DEFAULT_SOURCE = NEW_SCRAPER / "ads" / "generated_creatives"
DEFAULT_DEST = GIT_REPO / "generated_creatives"


def run(cmd, cwd=None):
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
        raise SystemExit(p.returncode)
    return p.stdout


def copy_tree(source: Path, dest: Path):
    if not source.exists():
        raise SystemExit(f"Source does not exist: {source}")

    copied = []
    for path in source.rglob("*"):
        if not path.is_file():
            continue

        rel = path.relative_to(source)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(str(rel))

    return copied


def write_manifest(dest: Path, copied):
    manifest = {
        "version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "source": str(DEFAULT_SOURCE),
        "files": copied,
        "repository": "jayantjos/trustfolio-daily-ads",
        "branch": "main",
        "purpose": "TrustFolio creative media bridge",
    }

    path = dest / "creative_publish_manifest.json"
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help="Generated creatives directory on the server",
    )
    parser.add_argument(
        "--dest",
        default=str(DEFAULT_DEST),
        help="Destination directory inside the GitHub working tree",
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Copy and commit locally, but do not push",
    )
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    dest = Path(args.dest).expanduser().resolve()

    if not GIT_REPO.exists():
        raise SystemExit(f"Git repository not found: {GIT_REPO}")

    print("=" * 88)
    print("TRUSTFOLIO CREATIVE GITHUB BRIDGE")
    print("=" * 88)
    print("Source:", source)
    print("Dest  :", dest)
    print()

    run(["git", "pull", "--ff-only", "origin", "main"], cwd=GIT_REPO)

    copied = copy_tree(source, dest)
    if not copied:
        raise SystemExit("No creative files found to publish.")

    manifest = write_manifest(GIT_REPO, copied)

    print()
    print("Copied files:", len(copied))
    print("Manifest    :", manifest)

    run(["git", "add", "generated_creatives", "creative_publish_manifest.json"], cwd=GIT_REPO)

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
        ["git", "commit", "-m", f"Publish TrustFolio creatives {stamp}"],
        cwd=GIT_REPO,
    )

    if not args.no_push:
        run(["git", "push", "origin", "main"], cwd=GIT_REPO)

    print()
    print("=" * 88)
    print("PUBLISH COMPLETE")
    print("=" * 88)
    print("Files pushed:", len(copied))
    print("GitHub repo : github.com/jayantjos/trustfolio-daily-ads")
    print("Branch      : main")
    print("=" * 88)


if __name__ == "__main__":
    main()
