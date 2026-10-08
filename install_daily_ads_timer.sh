#!/usr/bin/env bash
set -euo pipefail

BASE="$HOME/new_scraper"
RUN_SCRIPT="$BASE/ads/run_daily_ads.sh"
SYSTEMD_DIR="$HOME/.config/systemd/user"

mkdir -p "$SYSTEMD_DIR"

cat > "$SYSTEMD_DIR/trustfolio-daily-ads.service" <<EOF
[Unit]
Description=TrustFolio Daily Ads Pipeline
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/env bash ${RUN_SCRIPT}
WorkingDirectory=${BASE}
Environment=HOME=${HOME}
EOF

cat > "$SYSTEMD_DIR/trustfolio-daily-ads.timer" <<'EOF'
[Unit]
Description=Run TrustFolio Daily Ads every day at 03:00 India time

[Timer]
OnCalendar=*-*-* 03:00:00 Asia/Kolkata
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
EOF

chmod +x "$RUN_SCRIPT"
systemctl --user daemon-reload
systemctl --user enable --now trustfolio-daily-ads.timer

echo
echo "TrustFolio daily ads timer installed."
echo
systemctl --user --no-pager --full status trustfolio-daily-ads.timer || true

echo
echo "Next runs:"
systemctl --user list-timers --all | grep trustfolio-daily-ads || true

echo
echo "Manual run:"
echo "  $RUN_SCRIPT"

echo
echo "Logs:"
echo "  journalctl --user -u trustfolio-daily-ads.service -n 100 --no-pager"
