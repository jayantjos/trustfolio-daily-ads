#!/usr/bin/env bash
set -Eeuo pipefail
RELEASE="${1:?release path}"; SHA="${2:?commit SHA}"
TARGET="$HOME/new_scraper/ads"; ROOT="$HOME/trustfolio_deploy_backups"
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || exit 1
[[ -d "$TARGET" && -f "$TARGET/run_daily_ads.sh" ]] || { echo "Unexpected target"; exit 1; }
mkdir -p "$ROOT"
exec 9>"$HOME/.trustfolio_deploy.lock"
flock -n 9 || { echo "Deployment locked"; exit 1; }
mapfile -t FILES < <(grep -vE '^[[:space:]]*(#|$)' "$RELEASE/deploy/managed-files.txt")
(("${#FILES[@]}" > 0)) || exit 1
for f in "${FILES[@]}"; do
  [[ "$f" =~ ^[A-Za-z0-9_./-]+$ && "$f" != /* && "$f" != *..* ]] || exit 1
  [[ -f "$RELEASE/$f" && ! -L "$RELEASE/$f" ]] || exit 1
done
BACKUP="$ROOT/$(date -u +%Y%m%dT%H%M%SZ)_${SHA:0:12}"
mkdir -p "$BACKUP/previous"
: > "$BACKUP/existed.txt"
for f in "${FILES[@]}"; do
  if [[ -f "$TARGET/$f" ]]; then
    mkdir -p "$BACKUP/previous/$(dirname "$f")"
    cp -p "$TARGET/$f" "$BACKUP/previous/$f"
    printf '%s\n' "$f" >> "$BACKUP/existed.txt"
  fi
done
rollback() {
  echo "FAILED: restoring previous files"
  for f in "${FILES[@]}"; do
    if grep -Fxq "$f" "$BACKUP/existed.txt"; then
      cp -p "$BACKUP/previous/$f" "$TARGET/$f"
    else
      rm -f "$TARGET/$f"
    fi
  done
}
trap rollback ERR
for f in "${FILES[@]}"; do
  mkdir -p "$TARGET/$(dirname "$f")"
  cp "$RELEASE/$f" "$TARGET/$f.deploy-tmp"
  mv -f "$TARGET/$f.deploy-tmp" "$TARGET/$f"
done
for f in "${FILES[@]}"; do
  if [[ "$f" == *.py ]]; then "$HOME/venv/bin/python" -m py_compile "$TARGET/$f"; fi
done
printf '%s\n' "$SHA" > "$BACKUP/deployed_sha"
printf '%s\n' "$SHA" > "$TARGET/.trustfolio_deployed_sha"
trap - ERR
echo "DEPLOY_SUCCESS sha=$SHA backup=$BACKUP"
