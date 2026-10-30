#!/bin/bash
set -euo pipefail
cd "$HOME/apps/trustfolio/node-backend"
echo 'AVAILABILITY_FALLBACK_CROMA_AUDIT=READ_ONLY'
python3 - <<'PY'
from pathlib import Path
import re
files=['services/ProductAvailabilityPolicy.js','services/CromaLivePriceDirect.js','controllers/ProductController.js']
patterns={
 'services/ProductAvailabilityPolicy.js':re.compile(r'.',re.I),
 'services/CromaLivePriceDirect.js':re.compile(r'.',re.I),
 'controllers/ProductController.js':re.compile(r'live|fallback|price|refresh|invalidate|isActive|rank|top|shop|catalog',re.I)
}
for fname in files:
 p=Path(fname)
 print('===FILE='+fname+'===')
 if not p.exists(): print('NOT_FOUND');continue
 lines=p.read_text(errors='replace').splitlines()
 filt=[]
 for i,s in enumerate(lines):
  if patterns[fname].search(s):
   if fname=='controllers/ProductController.js':
    filt += list(range(max(0,i-1),min(len(lines),i+2)))
   else:filt.append(i)
 for i in sorted(set(filt))[:390]:
  line=lines[i]
  if re.search(r'\b(?:password|authorization|access_token|secret)\s*[:=]\s*["\x27]',line,re.I):line="[REDACTED]"
  print(f'{i+1:04} {line[:280]}')
 print('TOTAL_LINES=',len(lines))
PY
echo "READ_ONLY_COMPLETE=YES"
