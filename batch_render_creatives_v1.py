#!/usr/bin/env python3
import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = Path.home() / "new_scraper"
MANIFEST = BASE / "ads" / "creative_generation_manifest_v1.json"
OUT = BASE / "ads" / "generated_creatives" / "feed"
RENDERER = BASE / "ads" / "creative_renderer_v2.py"

sys.path.insert(0, str(RENDERER.parent))
import creative_renderer_v2 as renderer


def main():
    manifest_path = Path(sys.argv[1]) if len(sys.argv) > 1 else MANIFEST
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else OUT

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    ads = data.get("ads", [])
    if not ads:
        raise SystemExit("No ads found in creative generation manifest")

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    original_out = renderer.OUT_DIR
    renderer.OUT_DIR = out_dir

    print("=" * 88)
    print("TRUSTFOLIO PREMIUM IMAGE BATCH RENDERER V1")
    print("=" * 88)
    print("Ads        :", len(ads))
    print("Output     :", out_dir)
    print("Workers    : 4")
    print()

    failures = []

    def one(ad):
        renderer.render(ad)
        return ad.get("ad_id", "")

    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {pool.submit(one, ad): ad for ad in ads}
        for future in as_completed(jobs):
            ad = jobs[future]
            try:
                ad_id = future.result()
                print("[OK]", ad_id)
            except Exception as exc:
                ad_id = ad.get("ad_id", "")
                failures.append((ad_id, str(exc)))
                print("[FAIL]", ad_id, "->", exc)

    renderer.OUT_DIR = original_out

    print()
    print("=" * 88)
    print("BATCH RENDER COMPLETE")
    print("Generated :", len(ads) - len(failures))
    print("Failed    :", len(failures))
    print("Output    :", out_dir)
    print("=" * 88)

    if failures:
        for ad_id, err in failures[:20]:
            print("FAILURE:", ad_id, err)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
