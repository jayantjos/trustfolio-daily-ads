#!/usr/bin/env bash
# Promote a *tested, checksummed* copy of the site's own ranker with rollback.
set -Eeuo pipefail
RUN_KEY="${1:?run key required}"
EXPECTED_GIT_HEAD="6fa055ea951fb031fbb3072ccd3a9ddeb0ed4602"
BASE="$HOME/apps/trustfolio"
BACKEND="$BASE/node-backend"
STAGE="$HOME/trustfolio_site_live_budget_staging/$RUN_KEY"
BACKUP="$HOME/trustfolio_backend_backups/live-budget-$RUN_KEY"
CONTROLLER="$BACKEND/controllers/ProductController.js"
RANKER="$BACKEND/services/ProductRecommendationService.js"
HELPER="$BACKEND/services/LiveBudgetRecommendationService.js"
staged_controller="$STAGE/node-backend/controllers/ProductController.js"
staged_ranker="$STAGE/node-backend/services/ProductRecommendationService.js"
staged_helper="$STAGE/node-backend/services/LiveBudgetRecommendationService.js"
applied=0
had_helper=0

on_exit() {
  status=$?
  trap - EXIT
  if [[ "$status" -ne 0 && "$applied" -eq 1 ]]; then
    echo "ROLLBACK_TRIGGERED cause_exit_code=$status"
    cp -p "$BACKUP/ProductController.js" "$CONTROLLER" || true
    cp -p "$BACKUP/ProductRecommendationService.js" "$RANKER" || true
    if [[ "$had_helper" -eq 1 ]]; then
      cp -p "$BACKUP/LiveBudgetRecommendationService.js" "$HELPER" || true
    else
      rm -f "$HELPER" || true
    fi
    pm2 restart trustfolio-backend || true
    echo "ROLLBACK_ATTEMPTED original_files_restored=true"
  fi
  exit "$status"
}
trap on_exit EXIT

[[ -f "$staged_controller" && -f "$staged_ranker" && -f "$staged_helper" ]]
[[ "$(git -C "$BASE" branch --show-current)" == "main" ]]
[[ "$(git -C "$BASE" rev-parse HEAD)" == "$EXPECTED_GIT_HEAD" ]]
[[ -z "$(git -C "$BASE" status --porcelain -- node-backend/controllers/ProductController.js node-backend/services/ProductRecommendationService.js node-backend/services/LiveBudgetRecommendationService.js)" ]]
[[ ! -e "$HELPER" ]]  # fail instead of overwriting unknown work
cmp "$CONTROLLER" "$STAGE/original/ProductController.js"
cmp "$RANKER" "$STAGE/original/ProductRecommendationService.js"

# Stage all three files and verify them before restarting anything.
for f in "$staged_controller" "$staged_ranker" "$staged_helper"; do node --check "$f"; done
node --test "$STAGE/LiveBudgetRecommendationService.test.js"

mkdir -p "$BACKUP"
cp -p "$CONTROLLER" "$BACKUP/ProductController.js"
cp -p "$RANKER" "$BACKUP/ProductRecommendationService.js"
sha256sum "$BACKUP/"*.js > "$BACKUP/SHA256SUMS"
echo "BACKUP_READY=$BACKUP"
echo "EXISTING_GIT_HEAD=$EXPECTED_GIT_HEAD"

# Require that in-progress website files have not changed since backup.
cmp "$CONTROLLER" "$BACKUP/ProductController.js"
cmp "$RANKER" "$BACKUP/ProductRecommendationService.js"
applied=1
cp -p "$staged_ranker" "$RANKER"
cp -p "$staged_helper" "$HELPER"
cp -p "$staged_controller" "$CONTROLLER"
node --check "$CONTROLLER"
node --check "$RANKER"
node --check "$HELPER"
echo "BACKEND_FILES_COPIED_ONLY"
pm2 restart trustfolio-backend
sleep 3

# Validate real GET /api/products/top *after* its internal live-price overlay.
python3 - <<'PY'
import json,time
from urllib.parse import urlencode
from urllib.request import Request,urlopen
BASE="https://api.trustfolio.in/api/products/top"
queries=[
    {"category":"smartwatches","budget":2000,"limit":5},
    {"category":"washing-machines","budget":35000,"limit":5},
]
for query in queries:
    url=BASE+"?"+urlencode(query)
    response=None
    last=None
    for attempt in range(3):
        try:
            with urlopen(Request(url,headers={"Accept":"application/json","User-Agent":"TrustFolioBudgetLiveQA/1.0"}),timeout=70) as connection:
                if connection.status != 200: raise ValueError("non-200 status")
                response=json.loads(connection.read(500000))
            break
        except Exception as exc:
            last=exc
            time.sleep(2)
    if response is None: raise SystemExit("Backend smoke HTTP failed "+str(last))
    if response.get("success") is not True: raise SystemExit("Backend API failed")
    data=response.get("data") or {}
    products=data.get("products") or []
    assert data.get("livePriceRefreshCompleted") is True, "new refresh service not active"
    assert len(products)==5, f"Expected five live verified results for {query['category']}, got {len(products)}"
    ids=[str(p.get("id") or "") for p in products]
    assert all(ids) and len(set(ids))==5, "Duplicate or missing ids"
    assert [p.get("rank") for p in products]==[1,2,3,4,5], "rank order invalid"
    budget=int(query["budget"])
    prices=[float(p["price_inr"]) for p in products]
    assert all(0<p<=budget for p in prices), "Above-budget displayed live price"
    print("LIVE_BUDGET_SMOKE_PASSED",query["category"],"budget",budget,"prices",prices)
print("BOTH_WEBSITE_CATEGORIES_PASS")
PY
pm2 jlist | node -e 'let s="";process.stdin.on("data",b=>s+=b);process.stdin.on("end",()=>{const p=JSON.parse(s).find(x=>x.name==="trustfolio-backend");if(!p||p.pm2_env.status!=="online")process.exit(1);console.log("PM2_BACKEND_ONLINE")})'
applied=0
trap - EXIT
echo "DEPLOY_BUDGET_LIVE_SUCCESS"
echo "ROLLBACK_BACKUP=$BACKUP"
git -C "$BASE" status --short -- node-backend/controllers/ProductController.js node-backend/services/ProductRecommendationService.js node-backend/services/LiveBudgetRecommendationService.js
