#!/usr/bin/env bash
set -euo pipefail
source "$HOME/venv/bin/activate"
REPO="$HOME/daily_ads_git"
BASE="$HOME/new_scraper"
cd "$REPO"
git fetch origin reference-layout-v8
git show FETCH_HEAD:creative_renderer_reference_v8.py > "$BASE/ads/creative_renderer_reference_v8.py"
git show FETCH_HEAD:build_infographic_payload_v1.py > "$BASE/ads/build_infographic_payload_v1.py"
git show FETCH_HEAD:trustfolio_infographic_data_v1.py > "$BASE/ads/trustfolio_infographic_data_v1.py"
cd "$BASE"
python -m py_compile ads/creative_renderer_reference_v8.py
python ads/build_infographic_payload_v1.py
AD_ID="${1:-tf-aa5900f0c166}"
python ads/creative_renderer_reference_v8.py ads/trustfolio_infographic_payload_v1.json "$AD_ID"
echo
echo "QA only. Check the PNG before publishing any batch."
echo "Output: $BASE/ads/generated_creatives/feed/${AD_ID}_reference_v8_1024x1536.png"
