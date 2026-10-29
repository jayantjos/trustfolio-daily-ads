#!/usr/bin/env python3
"""Idempotent single-anchor safety patch. No MongoDB writes."""
from pathlib import Path
import argparse
import datetime
import os
import shutil
import subprocess
import sys

ROOT=Path.home()/'apps/trustfolio/node-backend/services'
FILE=ROOT/'ProductAvailabilityPolicy.js'
BACKUP_DIR=Path.home()/'backups/trustfolio-worker-parser-guard'
ANCHOR="  if (PERMANENT.has(status) || PERMANENT.has(availabilityStatus) || permanentRegex.test(statusRaw) || permanentRegex.test(availability))"
GUARD="""  // HTTP 200 with a parser-only missing listing is not a confirmed unavailable item.
  // Flipkart can serve valid product pages with prices loaded dynamically in the browser.
  if (http === 200 && !availability &&
      ['not_listed','not_found','not_available'].includes(status)) return 'transient';
"""
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--check',action='store_true')
    ap.add_argument('--apply',action='store_true')
    args=ap.parse_args()
    if not (args.check ^ args.apply):raise ValueError('exactly one of --check or --apply required')
    text=FILE.read_text('utf-8')
    if GUARD in text:
        print('PARSER_GUARD_ALREADY_INSTALLED=YES')
        return
    if text.count(ANCHOR)!=1:
        raise RuntimeError('unexpected production policy source; refusing patch')
    updated=text.replace(ANCHOR,GUARD+ANCHOR,1)
    temp=ROOT/'ProductAvailabilityPolicy.parser-guard-next.js'
    temp.write_text(updated,'utf-8')
    try:subprocess.run(['node','--check',str(temp)],check=True)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    if args.check:
        temp.unlink(missing_ok=True)
        print('PARSER_GUARD_DRY_RUN=PASS')
        print('PRODUCTION_CHANGED=NO')
        return
    backup=BACKUP_DIR/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup.mkdir(parents=True,exist_ok=False)
    shutil.copy2(FILE,backup/'ProductAvailabilityPolicy.js')
    os.replace(temp,FILE)
    print('PARSER_GUARD_BACKUP='+str(backup/'ProductAvailabilityPolicy.js'))
    print('PARSER_GUARD_INSTALLED=YES')
if __name__=='__main__':
    try:main()
    except Exception as exc:print('PARSER_GUARD_ERROR='+str(exc)[:220],file=sys.stderr);sys.exit(1)
