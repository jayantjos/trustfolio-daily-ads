#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${TRUSTFOLIO_MEDIA_DOMAIN:-media.trustfolio.in}"
MEDIA_ROOT="${TRUSTFOLIO_PUBLIC_MEDIA_ROOT:-$HOME/public_media}"
MEDIA_PORT="${TRUSTFOLIO_MEDIA_PORT:-8787}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo bash $0"
  exit 1
fi

if ! command -v nginx >/dev/null 2>&1; then
  echo "Nginx is not installed."
  echo "Install it first: apt-get update && apt-get install -y nginx"
  exit 1
fi

mkdir -p "$MEDIA_ROOT"

cat > "/etc/nginx/sites-available/${DOMAIN}" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:${MEDIA_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # Media is read-only from the public side.
        limit_except GET HEAD OPTIONS {
            deny all;
        }
    }
}
EOF

ln -sfn "/etc/nginx/sites-available/${DOMAIN}" "/etc/nginx/sites-enabled/${DOMAIN}"

nginx -t
systemctl reload nginx

echo
echo "Nginx HTTP proxy is configured for:"
echo "  http://${DOMAIN}/"
echo
echo "Upstream:"
echo "  http://127.0.0.1:${MEDIA_PORT}/"
echo
echo "Next: point the DNS A record for ${DOMAIN} to this server's public IP,"
echo "then run Certbot for HTTPS."
