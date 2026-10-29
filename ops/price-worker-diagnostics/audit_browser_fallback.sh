#!/usr/bin/env bash
set -euo pipefail
echo "=== Browser executable availability ==="
for x in chromium chromium-browser google-chrome google-chrome-stable firefox; do command -v "$x" || true; done
echo "=== Browser-related Node module availability ==="
cd "$HOME/apps/trustfolio/node-backend"
node <<'NODE'
for (const name of ['playwright','playwright-core','puppeteer','puppeteer-core','chrome-remote-interface','selenium-webdriver']) {
 try {console.log(name+'='+require.resolve(name));} catch(_) {console.log(name+'=NOT_INSTALLED');}
}
NODE
echo "=== Browser cache, sizes ==="
du -sh "$HOME/.cache/ms-playwright" "$HOME/.cache/puppeteer" 2>/dev/null || true
echo "=== Hardware ==="
free -m | sed -n '1,3p'
df -h "$HOME" | tail -1
echo "=== Product API env metadata (no tokens) ==="
node <<'NODE'
require('dotenv').config();
for(const k of ['PRICE_WORKER_URL','FLIPKART_AFFILIATE_ID','FLIPKART_AFFILIATE_TOKEN','FLIPKART_API_URL','BRIGHTDATA_API_URL','SCRAPEDO_TOKEN'])
 console.log(k+'='+Boolean(process.env[k]));
NODE
echo '=== Playwright cache executable candidates ==='
find "$HOME/.cache/ms-playwright" -maxdepth 5 -type f \( -name chrome -o -name chromium -o -name headless_shell -o -name firefox \) -print 2>/dev/null | head -12
echo '=== Python Playwright availability ==='
for py in python3 "$HOME/venv/bin/python" "$HOME/new_scraper/.venv/bin/python" "$HOME/apps/trustfolio/node-backend/.venv/bin/python"; do
  test -x "$py" || continue
  "$py" -c 'import importlib.util,sys;print(sys.executable,"PLAYWRIGHT_AVAILABLE="+str(importlib.util.find_spec("playwright") is not None))' || true
done
echo 'READ_ONLY=YES'
