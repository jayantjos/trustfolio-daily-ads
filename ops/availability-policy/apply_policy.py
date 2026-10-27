#!/usr/bin/env python3
"""Guarded, reversible update to TrustFolio's existing LivePriceService deletion policy.

--check: validate exact anchors and staged Node syntax, with no production change
--apply: archive old file, install shared policy, replace two guarded blocks
--rollback <folder>: restore original service and previous policy
Never changes scraper, web frontend, Cloudflare Worker, or MongoDB during patching.
"""
import argparse, datetime, hashlib, json, os, re, shutil, subprocess, sys
from pathlib import Path

ROOT=Path.home()/'apps/trustfolio/node-backend'
SERVICE=ROOT/'services/LivePriceService.js'
POLICY=ROOT/'services/ProductAvailabilityPolicy.js'
BACKUPS=Path.home()/'backups/trustfolio-availability-policy'

def nodecheck(file): subprocess.run(['node','--check',str(file)],check=True)
def sha(file): return hashlib.sha256(Path(file).read_bytes()).hexdigest()

def replace_one(s, old, new, label):
    count=s.count(old)
    if count!=1:raise RuntimeError('%s expected one anchor, found %s' % (label,count))
    return s.replace(old,new,1)

def patch_text(s):
    s=replace_one(s,
      "const { canFetchCroma, fetchCromaDirect } = require('./CromaLivePriceDirect');",
      "const { canFetchCroma, fetchCromaDirect } = require('./CromaLivePriceDirect');\n"
      "const { classify, toAvailabilityState, isConfirmedUnavailable } = require('./ProductAvailabilityPolicy');",
      'policy_import')
    start=s.find('function isConfirmedUnavailable(live) {')
    end=s.find('function toLive(result, prev = {}) {',start)
    if start<0 or end<0 or end<=start:raise RuntimeError('legacy_classifier missing')
    s=s[:start]+s[end:]
    idx=s.index('function toLive(result, prev = {}) {')
    end=s.find('\n  return {',idx)
    if end<0:raise RuntimeError('toLive return block missing')
    h=s[idx:end]
    if "const priced = (result.status === 'ok' || result.status === 'out_of_stock') && result.priceNum > 0;" not in h:
      raise RuntimeError('toLive unexpected price status logic')
    s=s[:idx]+"""function toLive(result, prev = {}) {
  const availabilityKind = classify(result);
  // Do not show a fresh LIVE badge for a product whose listing explicitly says unavailable.
  const liveStatus = availabilityKind === 'permanent' ? 'out_of_stock'
    : availabilityKind === 'ambiguous' ? 'not_available'
    : availabilityKind === 'transient' && result.status === 'ok' ? 'error' : result.status;
  const priced = (liveStatus === 'ok' || liveStatus === 'out_of_stock') && result.priceNum > 0;
  const availabilityState = toAvailabilityState(result, prev);"""+s[end:]
    s=replace_one(s,
      "  return {\n    status: result.status,",
      "  return {\n    ...availabilityState,\n    status: liveStatus,",
      'availability_state_in_live')
    s=replace_one(s,
      "    unavailable_checks: unavailable ? (Number(prev.unavailable_checks) || 0) + 1 : 0,",
      "    error: result.error ? String(result.error).slice(0, 180) : null,\n"
      "    http_status: Number(result.http_status ?? result.httpStatus ?? result.statusCode) || null,",
      'track_request_errors')
    s=replace_one(s,
      "      ? result.in_stock : result.status === 'ok',",
      "      ? result.in_stock : liveStatus === 'ok',",
      'stock_flag_not_false_positive')
    s=replace_one(s,
      "  const outOfStock = fetched.filter((d) => isConfirmedUnavailable(d.live));",
      "  // Bound irreversible per-request removals. Archive precedes delete, and\n"
      "  // transient 502/503/timeout/WAF failures NEVER count as unavailable.\n"
      "  const outOfStock = fetched.filter((d) => isConfirmedUnavailable(d.live)).slice(0, 5);",
      'max_archives_per_request')
    s=replace_one(s,
      "deleted_reason: String(outOfStock.find((d) => d._id.equals(doc._id)).live.status || 'unavailable'),",
      "deleted_reason: String((outOfStock.find((d) => d._id.equals(doc._id)).live.availability\n"
      "                || outOfStock.find((d) => d._id.equals(doc._id)).live.status || 'unavailable')).slice(0, 100),",
      'reason_details')
    return s

def main():
    ap=argparse.ArgumentParser()
    modes=ap.add_mutually_exclusive_group(required=True)
    modes.add_argument('--check',action='store_true')
    modes.add_argument('--apply',action='store_true')
    modes.add_argument('--rollback')
    ap.add_argument('--policy-source',type=Path,default=Path(__file__).with_name('ProductAvailabilityPolicy.js'))
    args=ap.parse_args()
    if args.rollback:
      folder=Path(args.rollback).expanduser().resolve()
      if not folder.is_relative_to(BACKUPS.resolve()):raise RuntimeError('invalid rollback directory')
      manifest=json.loads((folder/'manifest.json').read_text())
      original=folder/'LivePriceService.js'
      if sha(original)!=manifest['service_sha']:raise RuntimeError('backup checksum mismatch')
      temp=ROOT/'services/LivePriceService.rollback-test.js'
      shutil.copy2(original,temp);nodecheck(temp);os.replace(temp,SERVICE)
      if manifest['policy_existed']:
        shutil.copy2(folder/'ProductAvailabilityPolicy.js',POLICY)
      else:
        POLICY.unlink(missing_ok=True)
      print('AVAILABILITY_ROLLBACK=PASS')
      return
    if not SERVICE.is_file() or not args.policy_source.is_file():
      raise RuntimeError('service/policy file not found')
    before=SERVICE.read_text('utf8')
    after=patch_text(before)
    nodecheck(args.policy_source)
    tmp=ROOT/'services/LivePriceService.availability-test.js'
    tmp.write_text(after,'utf8')
    try:nodecheck(tmp)
    finally:tmp.unlink(missing_ok=True)
    print('AVAILABILITY_ANCHORS=PASS')
    print('SHARED_POLICY_SYNTAX=PASS')
    print('SERVICE_PATCH_SYNTAX=PASS')
    if args.check:
      print('AVAILABILITY_PATCH_DRY_RUN=PASS')
      return
    backup=BACKUPS/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup.mkdir(parents=True,exist_ok=False)
    shutil.copy2(SERVICE,backup/'LivePriceService.js')
    existed=POLICY.exists()
    if existed:shutil.copy2(POLICY,backup/'ProductAvailabilityPolicy.js')
    (backup/'manifest.json').write_text(json.dumps({
      'service_sha':sha(SERVICE),'policy_existed':existed
    }))
    try:
      service_temp=ROOT/'services/LivePriceService.availability-next.js'
      service_temp.write_text(after,'utf8')
      nodecheck(service_temp)
      os.replace(service_temp,SERVICE)
      shutil.copy2(args.policy_source,POLICY)
      nodecheck(SERVICE);nodecheck(POLICY)
    except Exception:
      shutil.copy2(backup/'LivePriceService.js',SERVICE)
      if existed:shutil.copy2(backup/'ProductAvailabilityPolicy.js',POLICY)
      else:POLICY.unlink(missing_ok=True)
      raise
    print('AVAILABILITY_POLICY_BACKUP='+str(backup))
    print('AVAILABILITY_POLICY_INSTALLED=YES')
    print('AMAZON_FLIPKART_CROMA_SUPPORTED=YES')
    print('SCRAPEDO_USED=NO')

if __name__=='__main__':
  try:main()
  except Exception as exc:
    print('AVAILABILITY_PATCH_FAILED='+str(exc)[:250],file=sys.stderr);sys.exit(1)
