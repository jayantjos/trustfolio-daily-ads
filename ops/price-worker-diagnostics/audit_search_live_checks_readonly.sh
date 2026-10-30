#!/bin/bash
set -euo pipefail
cd "$HOME/apps/trustfolio/node-backend"
python3 - <<'PY'
from pathlib import Path
import re
files=['services/LiveBudgetRecommendationService.js','models/ProductSummaryDto.js','utils/resolveProductPrice.js']
patterns=[r'live|price|cache|fresh|fallback|candidate|worker|fetch|status|delete|out_of_stock|in_stock']
pat=re.compile('|'.join(patterns),re.I)
for fname in files:
 print('===FILE='+fname+'===')
 f=Path(fname)
 if not f.exists():print('NOT_FOUND');continue
 lines=f.read_text(errors='replace').splitlines()
 ids=[i for i,l in enumerate(lines) if pat.search(l)]
 selected=set()
 for i in ids:
  for k in range(max(0,i-1),min(i+2,len(lines))):selected.add(k)
 for i in sorted(selected)[:360]:print(f'{i+1:04} {lines[i][:225]}')
 print('MATCH_COUNT=',len(ids),'TOTAL=',len(lines))
PY
echo 'LIVE_SEARCH_AUDIT=READ_ONLY'
