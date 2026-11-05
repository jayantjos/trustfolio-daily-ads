#!/usr/bin/env bash
set -euo pipefail
PACKAGE="/tmp/trustfolio-two-rollback-stage-42040330089"
APP="$HOME/apps/trustfolio"
WEB="$APP/trustfolio-main"
BACKUP="$(cat "$PACKAGE/backup-path.txt")"
[[ -f "$PACKAGE/STAGING_PASSED" && -f "$PACKAGE/web-staged/.next/BUILD_ID" && ! -f "$BACKUP/DEPLOYMENT_ATTEMPTED" ]]
cd "$APP"
sha256sum --check "$BACKUP/before.sha256"
sha256sum --check "$BACKUP/protected.sha256"
(cd "$BACKUP" && sha256sum --check build.sha256)
tar -xOf "$BACKUP/web-build.tgz" .next/BUILD_ID | cmp - "$WEB/.next/BUILD_ID"
python3 - "$PACKAGE" "$APP" <<'PY'
import sys,json,hashlib
from pathlib import Path
pkg,app=map(Path,sys.argv[1:])
for relative,item in json.loads((pkg/'manifest.json').read_text()).items():
 assert hashlib.sha256((pkg/'candidate'/item['file']).read_bytes()).hexdigest()==item['after_sha256']
staged=pkg/'web-staged';current=app/'trustfolio-main'
for folder in ['src','public']:
 a={str(p.relative_to(staged/folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (staged/folder).rglob('*') if p.is_file()}
 b={str(p.relative_to(current/folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (current/folder).rglob('*') if p.is_file()}
 if folder=='src':a.pop('components/ProductsTable.tsx');b.pop('components/ProductsTable.tsx')
 assert a==b,'Unrelated frontend source drift: '+folder
for f in ['package.json','next.config.js','.env']:
 assert (staged/f).read_bytes()==(current/f).read_bytes(),'Frontend configuration drift: '+f
print('PROMOTION_DRIFT_GUARDS_PASS')
PY
node -e 'const fs=require("fs"),cp=require("child_process");const p=JSON.parse(cp.execFileSync("pm2",["jlist"],{encoding:"utf8"})).map(x=>({name:x.name,pid:x.pid,status:x.pm2_env.status,restarts:x.pm2_env.restart_time}));fs.writeFileSync(process.argv[1],JSON.stringify(p,null,2));' "$BACKUP/pm2-deploy-before.json"
cat > "$BACKUP/recover.sh" <<'RECOVER'
#!/usr/bin/env bash
set -euo pipefail
BACKUP="$(cd "$(dirname "$0")" && pwd)"
[[ ! -f "$BACKUP/RECOVERY_COMPLETED" ]] || exit 0
APP="$HOME/apps/trustfolio"
cp "$BACKUP/files/node-backend/controllers/ProductController.js" "$APP/node-backend/controllers/"
cp "$BACKUP/files/node-backend/services/ProductRecommendationService.js" "$APP/node-backend/services/"
cp "$BACKUP/files/node-backend/services/LiveBudgetRecommendationService.js" "$APP/node-backend/services/"
cp "$BACKUP/files/trustfolio-main/src/components/ProductsTable.tsx" "$APP/trustfolio-main/src/components/ProductsTable.tsx"
RECOVERY="$(mktemp -d "$APP/trustfolio-main/.rollback-recovery.XXXXXX")"
tar -xzf "$BACKUP/web-build.tgz" -C "$RECOVERY"
if [[ -d "$APP/trustfolio-main/.next" ]]; then mv "$APP/trustfolio-main/.next" "$BACKUP/rejected-build"; fi
mv "$RECOVERY/.next" "$APP/trustfolio-main/.next"
rmdir "$RECOVERY"
cd "$APP"
sha256sum --check "$BACKUP/before.sha256"
sha256sum --check "$BACKUP/protected.sha256"
pm2 restart trustfolio-backend
pm2 restart trustfolio-web
node -e 'const p=JSON.parse(require("child_process").execFileSync("pm2",["jlist"],{encoding:"utf8"}));for(const name of ["trustfolio-backend","trustfolio-web"])if(p.find(x=>x.name===name)?.pm2_env.status!=="online")process.exit(1);console.log("RECOVERY_PM2_ONLINE");'
touch "$BACKUP/RECOVERY_COMPLETED"
RECOVER
chmod 700 "$BACKUP/recover.sh"
touch "$BACKUP/DEPLOYMENT_ATTEMPTED"
trap 'bash "$BACKUP/recover.sh"' ERR
cp "$PACKAGE/candidate/ProductController.js" node-backend/controllers/ProductController.js
cp "$PACKAGE/candidate/ProductRecommendationService.js" node-backend/services/ProductRecommendationService.js
cp "$PACKAGE/candidate/LiveBudgetRecommendationService.js" node-backend/services/LiveBudgetRecommendationService.js
cp "$PACKAGE/candidate/ProductsTable.tsx" trustfolio-main/src/components/ProductsTable.tsx
mv "$WEB/.next" "$BACKUP/pre-deploy-web-build"
cp -a "$PACKAGE/web-staged/.next" "$WEB/.next"
pm2 restart trustfolio-backend
pm2 restart trustfolio-web
python3 - "$PACKAGE" "$APP" <<'PY'
import sys,json,hashlib
from pathlib import Path
pkg,app=map(Path,sys.argv[1:])
for relative,item in json.loads((pkg/'manifest.json').read_text()).items():assert hashlib.sha256((app/relative).read_bytes()).hexdigest()==item['after_sha256']
print('DEPLOYED_PRE_OVERRIDE_HASHES_PASS')
PY
sha256sum --check "$BACKUP/protected.sha256"
trap - ERR
printf 'ROLLBACK_PROMOTED backup=%s\n' "$BACKUP"

