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
cp "$GIT_REPO/trustfolio_infographic_data_v1.py" "$BASE/ads/trustfolio_infographic_data_v1.py"
cp "$GIT_REPO/build_infographic_payload_v1.py" "$BASE/ads/build_infographic_payload_v1.py"
cp "$GIT_REPO/creative_renderer_v6.py" "$BASE/ads/creative_renderer_v6.py"
cp "$GIT_REPO/batch_render_creatives_v1.py" "$BASE/ads/batch_render_creatives_v1.py"
cp "$GIT_REPO/social_post_generator_v1.py" "$BASE/ads/social_post_generator_v1.py"
cp "$GIT_REPO/public_media_bridge_v1.py" "$BASE/ads/public_media_bridge_v1.py"
cp "$GIT_REPO/publish_creative_to_github.py" "$BASE/ads/publish_creative_to_github.py"
cp "$GIT_REPO/cleanup_creative_storage_v1.py" "$BASE/ads/cleanup_creative_storage_v1.py"

cd "$BASE"

export TRUSTFOLIO_PUBLIC_MEDIA_ROOT="$HOME/public_media"
export TRUSTFOLIO_PUBLIC_MEDIA_BASE_URL="https://media.trustfolio.in"
export TRUSTFOLIO_MEDIA_RETENTION_HOURS="${TRUSTFOLIO_MEDIA_RETENTION_HOURS:-72}"

echo "=== 1/8 V8 AD ENGINE ==="
python ads/daily_ad_engine_20_v8.py

echo "=== 2/8 LINK MANIFEST ==="
python ads/ad_link_manifest_v1.py

echo "=== 3/8 CREATIVE MANIFEST ==="
python ads/creative_generator_v1.py

echo "=== 4/9 INFOGRAPHIC PAYLOAD ==="
python ads/build_infographic_payload_v1.py

echo "=== 5/9 PREMIUM IMAGE ADS ==="
python ads/batch_render_creatives_v1.py

echo "=== 6/9 PUBLIC MEDIA ==="
python ads/public_media_bridge_v1.py

echo "=== 7/9 SOCIAL POST COPY ==="
python ads/social_post_generator_v1.py

echo "=== 8/9 GITHUB METADATA BRIDGE ==="
python ads/publish_creative_to_github.py

echo "=== 9/9 STORAGE CLEANUP ==="
python ads/cleanup_creative_storage_v1.py

echo "=== DAILY ADS PIPELINE COMPLETE ==="
