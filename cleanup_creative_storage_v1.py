#!/usr/bin/env python3
import os
import shutil
import time
from pathlib import Path

BASE = Path.home() / "new_scraper"
LOCAL_FEED = BASE / "ads" / "generated_creatives" / "feed"
PUBLIC_ROOT = Path(
    os.getenv(
        "TRUSTFOLIO_PUBLIC_MEDIA_ROOT",
        str(Path.home() / "public_media"),
    )
).expanduser().resolve()

RETENTION_HOURS = float(
    os.getenv("TRUSTFOLIO_MEDIA_RETENTION_HOURS", "72")
)
cutoff = time.time() - RETENTION_HOURS * 3600

if LOCAL_FEED.exists():
    shutil.rmtree(LOCAL_FEED)
    print("Deleted local rendered feed:", LOCAL_FEED)

deleted = 0
for path in PUBLIC_ROOT.rglob("*"):
    if not path.is_file():
        continue

    try:
        if path.stat().st_mtime < cutoff:
            path.unlink()
            deleted += 1
    except FileNotFoundError:
        pass

print(
    f"Deleted {deleted} public media files older than "
    f"{RETENTION_HOURS:g} hours."
)
print("Public media root:", PUBLIC_ROOT)
