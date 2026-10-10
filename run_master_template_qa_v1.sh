#!/usr/bin/env bash
set -euo pipefail
source "$HOME/venv/bin/activate"
REPO="$HOME/daily_ads_git"
BASE="$HOME/new_scraper"
cd "$REPO"
git pull --ff-only origin main
cp "$REPO/master_template_layout_v1.json" "$BASE/ads/"
cp "$REPO/master_template_renderer_v1.py" "$BASE/ads/"
cp "$REPO/creative_renderer_v6.py" "$BASE/ads/"
cp "$REPO/build_infographic_payload_v1.py" "$BASE/ads/"
cp "$REPO/trustfolio_infographic_data_v1.py" "$BASE/ads/"
cd "$BASE"
python -m py_compile ads/master_template_renderer_v1.py
python ads/build_infographic_payload_v1.py
AD_ID="${1:-tf-aa5900f0c166}"
python ads/master_template_renderer_v1.py ads/trustfolio_infographic_payload_v1.json "$AD_ID"
echo
echo "QA image is in: $BASE/ads/generated_creatives/feed/"
echo "Do not batch-publish until the rendered PNG is visually approved."
