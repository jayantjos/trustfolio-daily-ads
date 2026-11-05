#!/usr/bin/env bash
set -euo pipefail
PACKAGE="$1"
RUN_ID="$2"
APP="$HOME/apps/trustfolio"
BACKEND="$APP/node-backend"
WEB="$APP/trustfolio-main"
STAGED="/tmp/trustfolio-catalog-bypass-42001464650"
PREPARED="$HOME/trustfolio_backend_backups/catalog-bypass-prepare-42001835136"
BACKUP="$HOME/trustfolio_backend_backups/catalog-bypass-deploy-$RUN_ID"
[[ -f "$STAGED/web-staged/.next/BUILD_ID" && ! -e "$BACKUP" ]]
(cd "$PREPARED" && sha256sum --check backup.sha256)
cd "$BACKEND"
sha256sum --check "$STAGED/production.sha256"
cmp "$WEB/src/components/ProductsTable.tsx" "$PACKAGE/ProductsTable.original.tsx"
for name in ProductController.js LiveBudgetRecommendationService.js ProductsTable.tsx; do cmp "$PACKAGE/$name" "$STAGED/$name"; done
cmp "$PACKAGE/ProductsTable.tsx" "$STAGED/web-staged/src/components/ProductsTable.tsx"
node --check "$PACKAGE/ProductController.js"
node --check "$PACKAGE/LiveBudgetRecommendationService.js"
node --test "$PACKAGE/CatalogBypass.test.js"
NODE_PATH="$BACKEND/node_modules" node "$PACKAGE/staging.js" "$PACKAGE"
node "$PACKAGE/frontend.test.js" "$WEB" "$PACKAGE"
NODE_PATH="$BACKEND/node_modules" node "$PACKAGE/production-evidence.js" "$PACKAGE" before
node -e 'const fs=require("fs"),cp=require("child_process");const p=JSON.parse(cp.execFileSync("pm2",["jlist"],{encoding:"utf8"}));fs.writeFileSync(process.argv[1],JSON.stringify(p.map(x=>({name:x.name,pid:x.pid,status:x.pm2_env.status,restarts:x.pm2_env.restart_time}))));' "$PACKAGE/pm2-before.json"
mkdir -p "$BACKUP/backend/controllers" "$BACKUP/backend/services" "$BACKUP/frontend"
cp controllers/ProductController.js "$BACKUP/backend/controllers/"
cp services/LiveBudgetRecommendationService.js services/LivePriceService.js "$BACKUP/backend/services/"
cp "$WEB/src/components/ProductsTable.tsx" "$BACKUP/frontend/ProductsTable.tsx"
cp "$STAGED/production.sha256" "$BACKUP/production.sha256"
sha256sum "$WEB/src/components/ProductsTable.tsx" > "$BACKUP/frontend.sha256"
cp "$PACKAGE/catalog-before.json" "$PACKAGE/pm2-before.json" "$BACKUP/"
cat > "$BACKUP/rollback.sh" <<'ROLLBACK'
#!/usr/bin/env bash
set -euo pipefail
BACKUP="$(cd "$(dirname "$0")" && pwd)"
[[ ! -f "$BACKUP/ROLLBACK_COMPLETED" ]] || exit 0
APP="$HOME/apps/trustfolio"
cp "$BACKUP/backend/controllers/ProductController.js" "$APP/node-backend/controllers/"
cp "$BACKUP/backend/services/LiveBudgetRecommendationService.js" "$APP/node-backend/services/"
cp "$BACKUP/frontend/ProductsTable.tsx" "$APP/trustfolio-main/src/components/ProductsTable.tsx"
if [[ -d "$BACKUP/frontend/next-build" ]]; then
 if [[ -d "$APP/trustfolio-main/.next" ]]; then mv "$APP/trustfolio-main/.next" "$BACKUP/frontend/rejected-next-build"; fi
 mv "$BACKUP/frontend/next-build" "$APP/trustfolio-main/.next"
fi
cd "$APP/node-backend"
sha256sum --check "$BACKUP/production.sha256"
sha256sum --check "$BACKUP/frontend.sha256"
pm2 restart trustfolio-backend
pm2 restart trustfolio-web
touch "$BACKUP/ROLLBACK_COMPLETED"
node -e 'const p=JSON.parse(require("child_process").execFileSync("pm2",["jlist"],{encoding:"utf8"}));for(const name of ["trustfolio-backend","trustfolio-web"]){if(p.find(x=>x.name===name)?.pm2_env.status!=="online")process.exit(1);}console.log("ROLLBACK_HEALTH_PASS");'
ROLLBACK
chmod 700 "$BACKUP/rollback.sh"
trap 'bash "$BACKUP/rollback.sh"' ERR
cp "$PACKAGE/LiveBudgetRecommendationService.js" services/LiveBudgetRecommendationService.js
cp "$PACKAGE/ProductController.js" controllers/ProductController.js
cp "$PACKAGE/ProductsTable.tsx" "$WEB/src/components/ProductsTable.tsx"
mv "$WEB/.next" "$BACKUP/frontend/next-build"
cp -a "$STAGED/web-staged/.next" "$WEB/.next"
pm2 restart trustfolio-backend
pm2 restart trustfolio-web
node "$PACKAGE/production-api.js" "$PACKAGE" 'https://api.trustfolio.in'
NODE_PATH="$BACKEND/node_modules" node "$PACKAGE/production-evidence.js" "$PACKAGE" after
node - "$PACKAGE" <<'JS'
const fs=require('fs'),assert=require('assert/strict'),cp=require('child_process'),pkg=process.argv[2];
const before=JSON.parse(fs.readFileSync(pkg+'/pm2-before.json'));
const after=JSON.parse(cp.execFileSync('pm2',['jlist'],{encoding:'utf8'})).map(x=>({name:x.name,pid:x.pid,status:x.pm2_env.status,restarts:x.pm2_env.restart_time}));
for(const p of before){const row=after.find(x=>x.name===p.name);assert.equal(row.status,'online');if(!['trustfolio-backend','trustfolio-web'].includes(p.name))assert.deepEqual(row,p,'Unrelated service unchanged');}
fs.writeFileSync(pkg+'/pm2-after.json',JSON.stringify(after,null,2));console.log('PM2_HEALTH_PASS',JSON.stringify(after));
JS
sha256sum services/ProductRecommendationService.js services/LivePriceService.js
cp "$PACKAGE/production-api-after.json" "$PACKAGE/deployed-call-proof.json" "$PACKAGE/pm2-after.json" "$BACKUP/"
trap - ERR
printf 'PRODUCTION_PROMOTED backup=%s\n' "$BACKUP"

