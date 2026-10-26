#!/usr/bin/env bash
set -euo pipefail
root="$HOME/apps/trustfolio/trustfolio-main"
patch="$HOME/croma-ui-patch-once.py"
test -f "$patch"
test -d "$root/src/components"
test -d "$root/node_modules"
test -f "$root/package.json"
python3 "$patch" --root "$root"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
stage="$HOME/croma-ui-staging-$stamp"
backup="$HOME/backups/trustfolio-croma-ui/$stamp"
mkdir -p "$stage" "$backup"
echo "CROMA_UI_BACKUP_PATH=$backup"

# Prepare and build an isolated copy, leaving the running web app untouched.
(
  cd "$root"
  tar --exclude='./.next' --exclude='./node_modules' --exclude='./.git' -cf - .
) | (cd "$stage" && tar -xf -)
ln -s "$root/node_modules" "$stage/node_modules"
python3 "$patch" --root "$stage" --apply

cd "$stage"
export NEXT_TELEMETRY_DISABLED=1
if ! timeout 480 npm run build > "$backup/staging-build.log" 2>&1; then
  echo 'CROMA_UI_BUILD=FAILED'
  tail -35 "$backup/staging-build.log"
  exit 1
fi
test -f "$stage/.next/BUILD_ID"
test -f "$stage/.next/standalone/server.js"
echo 'CROMA_UI_STAGING_BUILD=PASS'

# A complete tested build now exists; only now touch the production website.
for f in src/components/ProductsTable.tsx src/services/api.service.ts src/types/product.ts; do
  mkdir -p "$backup/$(dirname "$f")"
  cp -p "$root/$f" "$backup/$f"
done
had_next=0
if test -d "$root/.next"; then had_next=1; fi
promoting=0
rollback() {
  rc=$?
  trap - ERR
  if test "$promoting" = 1; then
    for f in src/components/ProductsTable.tsx src/services/api.service.ts src/types/product.ts; do
      cp -p "$backup/$f" "$root/$f" || true
    done
    if test -d "$backup/.next"; then
      rm -rf "$root/.next"
      mv "$backup/.next" "$root/.next" || true
    fi
    pm2 restart trustfolio-web || true
    echo "CROMA_UI_ROLLBACK=EXECUTED"
  fi
  exit "$rc"
}
trap rollback ERR

promoting=1
if test "$had_next" = 1; then mv "$root/.next" "$backup/.next"; fi
mv "$stage/.next" "$root/.next"
for f in src/components/ProductsTable.tsx src/services/api.service.ts src/types/product.ts; do
  cp -p "$stage/$f" "$root/$f"
done

pm2 restart trustfolio-web
sleep 3
pm2 jlist | node -e 'let s="";process.stdin.on("data",x=>s+=x);process.stdin.on("end",()=>{let w=JSON.parse(s).find(x=>x.name==="trustfolio-web");if(!w||w.pm2_env.status!=="online")process.exit(2);console.log("TRUSTFOLIO_WEB_PM2_ONLINE=YES")})'
python3 "$patch" --root "$root"
test -f "$root/.next/BUILD_ID"
echo 'CROMA_UI_CHECKING_DEPLOY=PASS'
echo 'CROMA_LIVE_BADGE_VERIFIED_ONLY=YES'
trap - ERR
