#!/usr/bin/env bash
set -euo pipefail
BASE="$HOME/new_scraper"
REPO="$HOME/daily_ads_git"
AD_ID="$1"
if [ -z "$AD_ID" ]; then AD_ID="tf-aa5900f0c166"; fi
ASSET="$BASE/ads/assets/trustfolio_reference_master_v1.jpg"

if [ ! -f "$ASSET" ]; then
  echo "ERROR: master artwork asset missing:"
  echo "  $ASSET"
  echo "Copy trustfolio_reference_master_v1.jpg from the V2 bundle into ~/new_scraper/ads/assets/ first."
  exit 2
fi

source "$HOME/venv/bin/activate"
cd "$REPO"
git fetch origin master-template-integration-v2-clean
git show FETCH_HEAD:master_template_renderer_v2.py > "$BASE/ads/master_template_renderer_v2.py"
git show FETCH_HEAD:build_infographic_payload_v1.py > "$BASE/ads/build_infographic_payload_v1.py"
git show FETCH_HEAD:trustfolio_infographic_data_v1.py > "$BASE/ads/trustfolio_infographic_data_v1.py"

cd "$BASE"
python -m py_compile ads/master_template_renderer_v2.py
python ads/build_infographic_payload_v1.py
python ads/master_template_renderer_v2.py ads/trustfolio_infographic_payload_v1.json "$AD_ID"

echo
echo "QA ONLY. Do not publish or batch-render yet."
echo "Output: $BASE/ads/generated_creatives/feed/$AD_ID"_"master_v2_1024x1536.png"
