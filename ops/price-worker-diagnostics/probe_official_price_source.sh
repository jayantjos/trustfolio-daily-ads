#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/apps/trustfolio/node-backend"
echo "=== Official Flipkart product API probe (no auth tokens) ==="
curl -sS --max-time 8 --connect-timeout 3 -o /dev/null \
  -w 'FLIPKART_AFFILIATE_API_UNAUTH_HTTP=%{http_code}\n' \
  'https://affiliate-api.flipkart.net/affiliate/1.0/product.json?id=MOBHH2KYWG8UBBAF' || true
echo "=== Env flags present (no secret values) ==="
node <<'NODE'
const fs=require('fs');
const names=[
 ['backend', process.env.HOME+'/apps/trustfolio/node-backend/.env'],
 ['legacy_scraper', process.env.HOME+'/new_scraper/legacy_price/.env'],
 ['new_scraper', process.env.HOME+'/new_scraper/.env']
];
for(const [label,path] of names){
 const src=fs.existsSync(path)?fs.readFileSync(path,'utf8'):'';
 const keys=new Set([...src.matchAll(/^\s*([A-Z][A-Z0-9_]*)\s*=/gm)].map(m=>m[1]));
 for(const k of ['FLIPKART_AFFILIATE_ID','FLIPKART_AFFILIATE_TOKEN','FK_AFFILIATE_ID','FK_AFFILIATE_TOKEN',
   'SCRAPEDO_TOKEN','SCRAPE_DO_API_KEY','BRIGHTDATA_API_KEY']){
   console.log('SOURCE_CONFIG='+label+' '+k+'='+(keys.has(k)?'PRESENT':'ABSENT'));
 }
}
NODE
echo "READ_ONLY=YES"
