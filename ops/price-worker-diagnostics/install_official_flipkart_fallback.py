#!/usr/bin/env python3
"""Guarded install of optional official Flipkart exact-PID price fallback.

Keeps Amazon Worker, Flipkart Worker, Croma direct adapter and Mongo policy intact.
No credentials = original Worker behavior. No product writes during installation.
"""
import argparse, datetime, json, os, shutil, subprocess, sys
from pathlib import Path
ROOT=Path.home()/'apps/trustfolio/node-backend'
SERVICE=ROOT/'services/LivePriceService.js'
TARGET=ROOT/'services/FlipkartOfficialPrice.js'
BACKUPS=Path.home()/'backups/trustfolio-flipkart-official-fallback'
SOURCE_IMPORT="const { canFetchCroma, fetchCromaDirect } = require('./CromaLivePriceDirect');"
SOURCE_JOB="const job = (canFetchCroma(d) ? fetchCromaDirect(d) : fetchLive(workerItem(d)))"
SOURCE_FUNCTION="async function getLivePrices(ids) {"
ADAPTER_IMPORT="const { fetchFlipkartOfficial } = require('./FlipkartOfficialPrice');"
HELPER="""async function fetchFlipkartWithOfficialFallback(doc) {
  // First attempt remains the existing Cloudflare Worker.
  const workerResult = await fetchLive(workerItem(doc));
  if (workerResult && workerResult.status === 'ok') return workerResult;
  // Only a VERIFIED exact PID + variant + INR selling price may replace a worker error.
  const official = await fetchFlipkartOfficial(doc);
  return official && official.status === 'ok' ? official : workerResult;
}

"""
def patch(s):
  if ADAPTER_IMPORT in s:raise RuntimeError('already installed: refusing overwrite')
  replacements=[
    (SOURCE_IMPORT, SOURCE_IMPORT+'\n'+ADAPTER_IMPORT),
    (SOURCE_FUNCTION, HELPER+SOURCE_FUNCTION),
    (SOURCE_JOB,"const job = (canFetchCroma(d) ? fetchCromaDirect(d) :\n          String(d.platform || '').toLowerCase() === 'flipkart'\n            ? fetchFlipkartWithOfficialFallback(d) : fetchLive(workerItem(d)))")
  ]
  for old,new in replacements:
    if s.count(old)!=1:raise RuntimeError('production anchor mismatch '+old[:58])
    s=s.replace(old,new,1)
  return s
def syntax(p):subprocess.run(['node','--check',str(p)],check=True)
def main():
  ap=argparse.ArgumentParser()
  g=ap.add_mutually_exclusive_group(required=True)
  g.add_argument('--check',action='store_true')
  g.add_argument('--apply',action='store_true')
  g.add_argument('--rollback')
  ap.add_argument('--source',type=Path,default=Path(__file__).with_name('FlipkartOfficialPrice.js'))
  args=ap.parse_args()
  if args.rollback:
    b=Path(args.rollback).resolve()
    if not b.is_relative_to(BACKUPS.resolve()):raise RuntimeError('rollback outside backup directory')
    info=json.loads((b/'manifest.json').read_text())
    if not info.get('service'):raise RuntimeError('backup invalid')
    tmp=SERVICE.with_name('LivePriceService.restore-test.js')
    shutil.copy2(b/'LivePriceService.js',tmp);syntax(tmp);os.replace(tmp,SERVICE)
    if info.get('adapter_existed'):
      shutil.copy2(b/'FlipkartOfficialPrice.js',TARGET)
    else:TARGET.unlink(missing_ok=True)
    print('FLIPKART_OFFICIAL_ROLLBACK=PASS');return
  if not SERVICE.is_file() or not args.source.is_file():raise RuntimeError('missing source')
  if TARGET.exists():raise RuntimeError('adapter already present; refusing overwrite')
  original=SERVICE.read_text('utf8')
  final=patch(original)
  syntax(args.source)
  tmp=ROOT/'services/LivePriceService.flipkart-verify-next.js'
  tmp.write_text(final,'utf8')
  try:syntax(tmp)
  finally:tmp.unlink(missing_ok=True)
  print('FLIPKART_OFFICIAL_SOURCE_ANCHORS=PASS')
  print('FLIPKART_OFFICIAL_SYNTAX=PASS')
  if args.check:
    print('FLIPKART_OFFICIAL_DRY_RUN=PASS');return
  b=BACKUPS/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
  b.mkdir(parents=True,exist_ok=False)
  shutil.copy2(SERVICE,b/'LivePriceService.js')
  (b/'manifest.json').write_text(json.dumps({'service':True,'adapter_existed':False}))
  try:
    shutil.copy2(args.source,TARGET)
    tmp=SERVICE.with_name('LivePriceService.flipkart-install.js')
    tmp.write_text(final,'utf8')
    syntax(tmp);syntax(TARGET)
    os.replace(tmp,SERVICE)
  except Exception:
    shutil.copy2(b/'LivePriceService.js',SERVICE)
    TARGET.unlink(missing_ok=True)
    raise
  print('FLIPKART_OFFICIAL_BACKUP='+str(b))
  print('FLIPKART_OFFICIAL_FALLBACK_INSTALLED=YES')
  print('EXISTING_WORKER_AND_CROMA_UNCHANGED=YES')
if __name__=='__main__':
  try:main()
  except Exception as e:
    print('FLIPKART_INSTALL_ERROR='+str(e)[:280],file=sys.stderr)
    sys.exit(1)
