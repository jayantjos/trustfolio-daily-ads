#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/apps/trustfolio/node-backend"
python3 - <<'PY'
from pathlib import Path
files=[
 'services/LiveBudgetRecommendationService.js',
 'services/LivePriceService.js',
 'services/ProductAvailabilityPolicy.js',
 'routes/productRoutes.js',
 'routes/ProductRoutes.js'
]
for p in files:
 f=Path(p)
 if not f.exists():continue
 print('===== '+p+' =====')
 for n,s in enumerate(f.read_text(errors='replace').splitlines(),1):
  if any(k in s.lower() for k in ['api_key','secret=','token=','pass=']):s='[redacted]'
  print(f'{n:03} {s[:220]}')
PY
echo "===LIST ROUTES AND BACKEND_ENV_VAR_NAMES ONLY==="
find routes -maxdepth 2 -type f 2>/dev/null | grep -Ei 'product|price|live' | head -30 || true
pm2 jlist | node -e "let d='';process.stdin.on('data',x=>d+=x);process.stdin.on('end',()=>{try{for(const p of JSON.parse(d)){if(p.name==='trustfolio-backend'){const v=p.pm2_env||{};console.log('BACKEND_PM2_WORKER_URL_SET='+Boolean(v.PRICE_WORKER_URL));console.log('BACKEND_PM2_WORKER_KEY_SET='+Boolean(v.PRICE_WORKER_KEY));console.log('BACKEND_PM2_ENV_NAMES='+Object.keys(v).filter(x=>/WORKER|CROMA|LIVE_PRICE/.test(x)).sort().join(','));}}}catch(e){console.log('PM2_ENV_INSPECTION_FAIL')}})"
