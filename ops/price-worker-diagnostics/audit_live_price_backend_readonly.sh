#!/bin/bash
set -euo pipefail
cd "$HOME/apps/trustfolio/node-backend"
echo "BACKEND_AUDIT=READ_ONLY"
for file in services/LivePriceService.js scripts/trustfolio-category-price-watcher.js; do
 if [ ! -f "$file" ]; then echo "FILE_NOT_FOUND=$file"; continue; fi
 echo "===FILE=$file==="
 FILE="$file" python3 - <<'PY'
import os,re
p=os.environ['FILE']
lines=open(p,encoding='utf8',errors='replace').read().splitlines()
patterns=[
 r'out_of_stock|out.of.stock|unavailable|not_available|discontinued|sold.out',
 r'502|mass_delete|two.fresh|consecutive|not_listed|not_found',
 r'priceNum|price_inr|fallback|cached|FRESH_MS|MAX_IDS|WORKER_TIMEOUT_MS',
 r'PRICE_WORKER_URL|PRICE_WORKER_KEY|workerItem|fetchLive|live.price',
 r'updateOne|findByIdAndUpdate|deleteOne|deleteMany|bulkWrite|archive',
 r'croma|CROMA|priceRange|category.range|refreshRange'
]
found=[]
for i,s in enumerate(lines):
 if any(re.search(p,s,re.I) for p in patterns): found.append(i)
selected=set()
for i in found:
 for j in range(max(0,i-2),min(len(lines),i+3)): selected.add(j)
# Never output secrets, env-file contents or embedded credentials.
for i in sorted(selected)[:370]:
 s=lines[i]
 if re.search(r'(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*["\x27][A-Za-z0-9]',s):
  s='[redacted credential-bearing line]'
 print(f'{i+1:04} {s[:235]}')
print('MATCHED_LINE_COUNT=',len(found),'TOTAL_LINES=',len(lines))
PY
done
echo '=== LIVE PRICE RELATED ROUTE NAMES ==='
find routes controllers services -maxdepth 2 -type f \( -name '*.js' -o -name '*.ts' \) 2>/dev/null | grep -Ei 'price|product|croma|availab' | head -45
echo "BACKEND_AUDIT_COMPLETE=YES"
