#!/usr/bin/env bash
set -euo pipefail
PACKAGE="$1"
RUN_ID="$2"
APP="$HOME/apps/trustfolio"
WEB="$APP/trustfolio-main"
BACKEND="$APP/node-backend"
BACKUP="$HOME/trustfolio_backend_backups/two-smartphone-rollback-$RUN_ID"
mkdir -p "$PACKAGE/before" "$BACKUP/files"
python3 - "$PACKAGE" "$APP" "$BACKUP" <<'PY'
import sys,json,hashlib,shutil
from pathlib import Path
pkg,app,backup=map(Path,sys.argv[1:])
manifest=json.loads((pkg/'manifest.json').read_text())
for relative,item in manifest.items():
 current=app/relative;candidate=pkg/'candidate'/item['file'];reference=Path.home()/'trustfolio_backend_backups'/item['backup_source']
 assert hashlib.sha256(current.read_bytes()).hexdigest()==item['before_sha256'],'Current production drift: '+relative
 assert hashlib.sha256(candidate.read_bytes()).hexdigest()==item['after_sha256'],'Candidate drift: '+relative
 assert candidate.read_bytes()==reference.read_bytes(),'Verified pre-change source mismatch'
 target=backup/'files'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(current,target)
 shutil.copy2(current,pkg/'before'/item['file'])
(backup/'manifest.json').write_text(json.dumps(manifest,indent=2))
print('CURRENT_AND_PRE_OVERRIDE_CHECKSUMS_PASS')
PY
cd "$APP"
sha256sum node-backend/services/LivePriceService.js node-backend/scripts/trustfolio-category-price-watcher.js node-backend/.env > "$BACKUP/protected.sha256"
sha256sum node-backend/controllers/ProductController.js node-backend/services/ProductRecommendationService.js node-backend/services/LiveBudgetRecommendationService.js trustfolio-main/src/components/ProductsTable.tsx > "$BACKUP/before.sha256"
tar -C "$WEB" --exclude=.next/cache -czf "$BACKUP/web-build.tgz" .next
(cd "$BACKUP" && sha256sum web-build.tgz > build.sha256 && sha256sum --check build.sha256)
node -e 'const fs=require("fs"),cp=require("child_process");const p=JSON.parse(cp.execFileSync("pm2",["jlist"],{encoding:"utf8"})).map(x=>({name:x.name,pid:x.pid,status:x.pm2_env.status,restarts:x.pm2_env.restart_time}));fs.writeFileSync(process.argv[1],JSON.stringify(p,null,2));console.log("PM2_BEFORE",JSON.stringify(p));' "$BACKUP/pm2-before.json"
printf '%s' "$BACKUP" > "$PACKAGE/backup-path.txt"
for name in ProductController.js ProductRecommendationService.js LiveBudgetRecommendationService.js; do node --check "$PACKAGE/candidate/$name"; done
node --test "$PACKAGE/candidate/"*.test.js
cd "$BACKEND"
NODE_PATH="$BACKEND/node_modules" node "$PACKAGE/staging.js" "$PACKAGE"
node "$PACKAGE/frontend.test.cjs" "$WEB" "$PACKAGE"
mkdir -p "$PACKAGE/web-staged"
rsync -a --exclude=node_modules --exclude=.next --exclude=.git "$WEB/" "$PACKAGE/web-staged/"
ln -s "$WEB/node_modules" "$PACKAGE/web-staged/node_modules"
cp "$PACKAGE/candidate/ProductsTable.tsx" "$PACKAGE/web-staged/src/components/ProductsTable.tsx"
(cd "$PACKAGE/web-staged" && npm run build)
cd "$APP"
sha256sum --check "$BACKUP/before.sha256"
sha256sum --check "$BACKUP/protected.sha256"
cp "$PACKAGE/staging.json" "$BACKUP/staging.json"
touch "$PACKAGE/STAGING_PASSED"
printf 'STAGING_ALL_GATES_PASS backup=%s\n' "$BACKUP"

