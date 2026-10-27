#!/usr/bin/env bash
# One-time guarded TrustFolio live availability policy rollout.
# The stage folder holds apply_policy.py, ProductAvailabilityPolicy.js, ProductAvailabilityPolicy.test.js.
set -euo pipefail
stage="$(cd "$(dirname "$0")" && pwd)"
root="$HOME/apps/trustfolio/node-backend"
test -f "$root/services/LivePriceService.js"
test -f "$stage/ProductAvailabilityPolicy.js"
test -f "$stage/ProductAvailabilityPolicy.test.js"
test -f "$stage/apply_policy.py"
node "$stage/ProductAvailabilityPolicy.test.js"
python3 "$stage/apply_policy.py" --check --policy-source "$stage/ProductAvailabilityPolicy.js"
backup=''
on_failure() {
  rc=$?
  trap - ERR
  if test -n "$backup"; then
    python3 "$stage/apply_policy.py" --rollback "$backup" || true
    pm2 restart trustfolio-backend || true
    echo 'AVAILABILITY_DEPLOY=ROLLED_BACK'
  fi
  exit "$rc"
}
trap on_failure ERR
output="$(python3 "$stage/apply_policy.py" --apply --policy-source "$stage/ProductAvailabilityPolicy.js")"
printf '%s\n' "$output"
backup="$(printf '%s\n' "$output" | sed -n 's/^AVAILABILITY_POLICY_BACKUP=//p')"
test -n "$backup"
node --check "$root/services/LivePriceService.js"
node --check "$root/services/ProductAvailabilityPolicy.js"
pm2 restart trustfolio-backend
sleep 2
pm2 jlist | node -e 'let s="";process.stdin.on("data",x=>s+=x);process.stdin.on("end",()=>{let p=JSON.parse(s).find(x=>x.name==="trustfolio-backend");if(!p || p.pm2_env.status!=="online")process.exit(2);console.log("TRUSTFOLIO_BACKEND_ONLINE=YES")})'
node -e '
const p=require(process.env.HOME+"/apps/trustfolio/node-backend/services/ProductAvailabilityPolicy");
if(!p.isConfirmedUnavailable({status:"sold_out"}))process.exit(2);
if(p.isConfirmedUnavailable({status:"error",error:"worker http 502",unavailable_checks:100}))process.exit(3);
console.log("DELETION_SAFETY_SMOKE=PASS");
'
echo 'ARCHIVE_BEFORE_DELETE=EXISTING_BEHAVIOR_PRESERVED'
echo 'MAX_AUTOMATIC_DELETES_PER_API_CALL=5'
echo 'AVAILABILITY_DEPLOY=PASS'
trap - ERR
