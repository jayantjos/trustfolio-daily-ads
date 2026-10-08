#!/usr/bin/env python3
"""
Public media bridge for TrustFolio creatives.

The web server should expose PUBLIC_MEDIA_ROOT at PUBLIC_MEDIA_BASE_URL.
Example:
  PUBLIC_MEDIA_ROOT=/home/scraperuser/public_media
  PUBLIC_MEDIA_BASE_URL=https://media.trustfolio.in

This script copies generated creative files, preserves their relative paths,
and writes a URL manifest for Metricool/public publishing.
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

NEW_SCRAPER = Path.home() / "new_scraper"
SOURCE = NEW_SCRAPER / "ads" / "generated_creatives"

PUBLIC_MEDIA_ROOT = Path(
    os.getenv("TRUSTFOLIO_PUBLIC_MEDIA_ROOT", str(Path.home() / "public_media"))
).expanduser().resolve()

PUBLIC_MEDIA_BASE_URL = os.getenv(
    "TRUSTFOLIO_PUBLIC_MEDIA_BASE_URL", ""
).rstrip("/")

MANIFEST_PATH = NEW_SCRAPER / "ads" / "public_media_manifest_v1.json"


def main():
    if not SOURCE.exists():
        raise SystemExit(f"Source directory does not exist: {SOURCE}")

    if not PUBLIC_MEDIA_BASE_URL:
        raise SystemExit(
            "Set TRUSTFOLIO_PUBLIC_MEDIA_BASE_URL, e.g. "
            "https://media.trustfolio.in"
        )

    copied = []
    for src in SOURCE.rglob("*"):
        if not src.is_file():
            continue

        rel = src.relative_to(SOURCE)
        dst = PUBLIC_MEDIA_ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

        copied.append({
            "relative_path": rel.as_posix(),
            "local_path": str(dst),
            "public_url": f"{PUBLIC_MEDIA_BASE_URL}/{rel.as_posix()}",
            "bytes": dst.stat().st_size,
        })

    manifest = {
        "version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "source": str(SOURCE),
        "public_root": str(PUBLIC_MEDIA_ROOT),
        "public_base_url": PUBLIC_MEDIA_BASE_URL,
        "files": copied,
    }

    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 88)
    print("TRUSTFOLIO PUBLIC MEDIA BRIDGE V1")
    print("=" * 88)
    print("Source :", SOURCE)
    print("Root   :", PUBLIC_MEDIA_ROOT)
    print("Base   :", PUBLIC_MEDIA_BASE_URL)
    print("Files  :", len(copied))
    print("Manifest:", MANIFEST_PATH)
    if copied:
        print()
        print("Sample URL:", copied[0]["public_url"])
    print("=" * 88)


if __name__ == "__main__":
    main()
