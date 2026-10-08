#!/usr/bin/env bash
set -euo pipefail

PUBLIC_ROOT="${TRUSTFOLIO_PUBLIC_MEDIA_ROOT:-$HOME/public_media}"
PORT="${TRUSTFOLIO_MEDIA_PORT:-8787}"

mkdir -p "$PUBLIC_ROOT"

echo "TrustFolio public media root: $PUBLIC_ROOT"
echo "Local media server port      : $PORT"
echo
echo "One-time local test:"
echo "  python3 -m http.server $PORT --bind 127.0.0.1 --directory \"$PUBLIC_ROOT\""
echo
echo "After starting the server, verify locally:"
echo "  curl -I http://127.0.0.1:$PORT/"
echo
echo "For Metricool, expose this directory at a stable HTTPS URL such as:"
echo "  https://media.trustfolio.in/"
echo
echo "Required reverse-proxy mapping:"
echo "  https://media.trustfolio.in/  ->  http://127.0.0.1:$PORT/"
echo
echo "Then export:"
echo "  export TRUSTFOLIO_PUBLIC_MEDIA_ROOT=\"$PUBLIC_ROOT\""
echo "  export TRUSTFOLIO_PUBLIC_MEDIA_BASE_URL=\"https://media.trustfolio.in\""
echo
echo "Finally publish generated files:"
echo "  python ~/new_scraper/ads/public_media_bridge_v1.py"
