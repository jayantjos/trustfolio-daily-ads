#!/usr/bin/env bash
set -euo pipefail
PACKAGE="$1"
APP="$HOME/apps/trustfolio"
BACKEND="$APP/node-backend"
WEB="$APP/trustfolio-main"
cd "$BACKEND"
printf 'PRODUCTION_HEAD='
git rev-parse HEAD
sha256sum controllers/ProductController.js services/LiveBudgetRecommendationService.js services/ProductRecommendationService.js services/LivePriceService.js > "$PACKAGE/production.sha256"
cat "$PACKAGE/production.sha256"
python3 - "$PACKAGE" "$WEB" <<'PY'
import hashlib,sys
from pathlib import Path
package,web=map(Path,sys.argv[1:])
expected={'controllers/ProductController.js':'453c4ff83d1b03aaf4ae97adef5f06f81e5547a315c9f966460e92e6af1d2842','services/LiveBudgetRecommendationService.js':'e26856f73df8bc66bcc0e8d0002569f9eb8c61d5eeca7f6b84cd7e22ccbfc232','services/ProductRecommendationService.js':'4668c32c090ca43daacb2226e680540eb059fbbc7e3209e77b11ff871fe9bd67','services/LivePriceService.js':'03d5c3c8ac73f7df281162bdaea467fef4f94859427938db1fbde65fef637f0d'}
for name,digest in expected.items():
 assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest, 'Production revision drift '+name
assert (web/'src/components/ProductsTable.tsx').read_text().rstrip()==(package/'ProductsTable.original.tsx').read_text().rstrip(), 'Frontend revision drift'
print('REVISION_GUARDS_PASS')
PY
node --check "$PACKAGE/ProductController.js"
node --check "$PACKAGE/LiveBudgetRecommendationService.js"
node --test "$PACKAGE/CatalogBypass.test.js"
NODE_PATH="$BACKEND/node_modules" node "$PACKAGE/staging.js" "$PACKAGE"
node "$PACKAGE/frontend.test.js" "$WEB" "$PACKAGE"
mkdir -p "$PACKAGE/web-staged"
rsync -a --exclude=node_modules --exclude=.next --exclude=.git "$WEB/" "$PACKAGE/web-staged/"
ln -s "$WEB/node_modules" "$PACKAGE/web-staged/node_modules"
cp "$PACKAGE/ProductsTable.tsx" "$PACKAGE/web-staged/src/components/ProductsTable.tsx"
cd "$PACKAGE/web-staged"
npm run build
cd "$BACKEND"
sha256sum --check "$PACKAGE/production.sha256"
node -e 'const p=JSON.parse(require("child_process").execFileSync("pm2",["jlist"],{encoding:"utf8"}));console.log("PM2_HEALTH",JSON.stringify(p.map(x=>({name:x.name,status:x.pm2_env.status,restarts:x.pm2_env.restart_time}))));'
printf 'STAGING_ONLY_PASS no production files changed, no PM2 restart\n'
