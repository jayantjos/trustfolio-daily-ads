#!/usr/bin/env bash
set -euo pipefail

MEDIA_ROOT="${TRUSTFOLIO_PUBLIC_MEDIA_ROOT:-$HOME/public_media}"
MEDIA_PORT="${TRUSTFOLIO_MEDIA_PORT:-8787}"

mkdir -p "$MEDIA_ROOT"
mkdir -p "$HOME/.config/systemd/user"

cat > "$HOME/.config/systemd/user/trustfolio-media.service" <<EOF
[Unit]
Description=TrustFolio Public Creative Media Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 -m http.server ${MEDIA_PORT} --bind 127.0.0.1 --directory ${MEDIA_ROOT}
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now trustfolio-media.service

echo
echo "Local media server:"
echo "  http://127.0.0.1:${MEDIA_PORT}/"
echo
echo "Service status:"
systemctl --user --no-pager --full status trustfolio-media.service || true

echo
echo "If this server must survive logout/reboot:"
echo "  sudo loginctl enable-linger $(whoami)"
echo
echo "Next, point media.trustfolio.in DNS to this server and configure"
echo "Nginx/Apache/Caddy HTTPS reverse proxy to 127.0.0.1:${MEDIA_PORT}."
