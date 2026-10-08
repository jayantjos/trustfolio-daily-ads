#!/usr/bin/env bash
set -euo pipefail

BASE="$HOME/new_scraper"
GIT_REPO="$HOME/daily_ads_git"

source "$HOME/venv/bin/activate"

cd "$GIT_REPO"
git pull --ff-only origin main

cp "$GIT_REPO/daily_ad_engine_20_v8.py" "$BASE/ads/daily_ad_engine_20_v8.py"
cp "$GIT_REPO/ad_link_manifest_v1.py" "$BASE/ads/ad_link_manifest_v1.py"
cp "$GIT_REPO/creative_generator_v1.py" "$BASE/ads/creative_generator_v1.py"
cp "$GIT_REPO/creative_renderer_v2.py" "$BASE/ads/creative_renderer_v2.py"
cp "$GIT_REPO/batch_render_creatives_v1.py" "$BASE/ads/batch_render_creatives_v1.py"
cp "$GIT_REPO/public_media_bridge_v1.py" "$BASE/ads/public_media_bridge_v1.py"
cp "$GIT_REPO/publish_creative_to_github.py" "$BASE/ads/publish_creative_to_github.py"

cd "$BASE"

echo "=== 1/7 V8 AD ENGINE ==="
python ads/daily_ad_engine_20_v8.py

echo "=== 2/7 LINK MANIFEST ==="
python ads/ad_link_manifest_v1.py

echo "=== 3/7 CREATIVE MANIFEST ==="
python ads/creative_generator_v1.py

echo "=== 4/7 PREMIUM IMAGE ADS ==="
python ads/batch_render_creatives_v1.py

echo "=== 5/7 PUBLIC MEDIA ==="
export TRUSTFOLIO_PUBLIC_MEDIA_ROOT="$HOME/public_media"
export TRUSTFOLIO_PUBLIC_MEDIA_BASE_URL="https://media.trustfolio.in"
python ads/public_media_bridge_v1.py

echo "=== 6/7 GITHUB BRIDGE ==="
python ads/publish_creative_to_github.py

echo "=== 7/7 DONE ==="
echo "Daily ad pipeline completed."
