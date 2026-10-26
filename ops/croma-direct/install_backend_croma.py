#!/usr/bin/env python3
"""Guarded VPS-only Croma adapter installation for TrustFolio backend.

--check: strict source-anchor validation and syntax check, no writes.
--apply: backup, install direct Croma adapter, patch only necessary hooks.
--rollback: restore exact saved LivePriceService.js and remove new adapter.
Never changes worker, MongoDB, app frontend or scraper.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path.home() / 'apps/trustfolio/node-backend'
SERVICE = ROOT / 'services/LivePriceService.js'
ADAPTER = ROOT / 'services/CromaLivePriceDirect.js'
BACKUPS = Path.home() / 'backups/trustfolio-croma-direct'

REPLACES = [
    (
        "const mongoose = require('mongoose');",
        "const mongoose = require('mongoose');\n"
        "const { canFetchCroma, fetchCromaDirect } = require('./CromaLivePriceDirect');",
        'croma import'
    ),
    (
        "platform_product_id: 1, price_inr: 1, live: 1,",
        "platform_product_id: 1, title: 1, brand: 1, category: 1, price_inr: 1, live: 1,",
        'Mongo projection includes title'
    ),
    (
        "  const due = WORKER_URL\n"
        "    ? docs.filter((d) => {\n"
        "      const checked = d.live && d.live.checked_at ? new Date(d.live.checked_at).getTime() : 0;\n"
        "      return workerItem(d) && now - checked > FRESH_MS;\n"
        "    })\n"
        "    : [];",
        "  const due = docs.filter((d) => {\n"
        "    const checked = d.live && d.live.checked_at ? new Date(d.live.checked_at).getTime() : 0;\n"
        "    // Croma uses direct API; Amazon/Flipkart retain Cloudflare Worker.\n"
        "    return ((WORKER_URL && workerItem(d)) || canFetchCroma(d)) && now - checked > FRESH_MS;\n"
        "  });",
        'Croma-aware due filter'
    ),
    (
        "const job = fetchLive(workerItem(d)).catch((e) => ({ status: 'error', error: e.message }));",
        "const job = (canFetchCroma(d) ? fetchCromaDirect(d) : fetchLive(workerItem(d)))\n"
        "          .catch((e) => ({ status: 'error', error: e.message }));",
        'Croma fetch routing'
    ),
    (
        "    in_stock: result.status === 'ok',",
        "    in_stock: Object.prototype.hasOwnProperty.call(result, 'in_stock')\n"
        "      ? result.in_stock : result.status === 'ok',",
        'Unknown Croma stock remains null'
    ),
    (
        "supported: Boolean(workerItem(d)),",
        "supported: Boolean(workerItem(d)) || canFetchCroma(d),",
        'Croma API support metadata'
    )
]

def sha(data):
    return hashlib.sha256(data).hexdigest()

def transform(source):
    for before, after, label in REPLACES:
        if source.count(before) != 1:
            raise RuntimeError('%s: expected exactly one anchor, found %d' % (
                label, source.count(before)
            ))
        source = source.replace(before, after, 1)
    return source

def syntax(filename):
    subprocess.run(['node', '--check', str(filename)], check=True)

def main():
    parser = argparse.ArgumentParser()
    p = parser.add_mutually_exclusive_group(required=True)
    p.add_argument('--check', action='store_true')
    p.add_argument('--apply', action='store_true')
    p.add_argument('--rollback', metavar='BACKUP_DIR')
    parser.add_argument('--adapter-source', type=Path, default=Path(__file__).with_name('CromaLivePriceDirect.js'))
    args = parser.parse_args()

    if args.rollback:
        folder = Path(args.rollback).expanduser().resolve()
        if not folder.is_relative_to(BACKUPS.resolve()):
            raise RuntimeError('backup path not under approved directory')
        manifest = json.loads((folder / 'manifest.json').read_text())
        restored = (folder / 'LivePriceService.js').read_bytes()
        if sha(restored) != manifest['service_sha_before']:
            raise RuntimeError('backup digest verification failed')
        tmp = SERVICE.with_suffix('.js.restore-temp')
        tmp.write_bytes(restored)
        syntax(tmp)
        os.replace(tmp, SERVICE)
        if not manifest.get('adapter_existed', False):
            ADAPTER.unlink(missing_ok=True)
        else:
            shutil.copy2(folder / 'CromaLivePriceDirect.js', ADAPTER)
        print('CROMA_ROLLBACK=PASS')
        return

    if not SERVICE.is_file() or not args.adapter_source.is_file():
        raise RuntimeError('missing production service or source adapter')
    if ADAPTER.exists():
        raise RuntimeError('Croma adapter already exists; refusing overwrite')
    orig = SERVICE.read_bytes()
    transformed = transform(orig.decode('utf8'))
    syntax(args.adapter_source)
    print('SIX_PATCH_ANCHORS=PASS')
    print('CROMA_ADAPTER_SYNTAX=PASS')
    if args.check:
        print('PATCH_DRY_RUN=PASS')
        print('MONGODB_WRITES=0')
        return

    folder = BACKUPS / datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'LivePriceService.js').write_bytes(orig)
    (folder / 'manifest.json').write_text(json.dumps({
        'service_sha_before': sha(orig), 'adapter_existed': False
    }))
    try:
        tmp = SERVICE.with_suffix('.js.croma-temp')
        tmp.write_text(transformed, encoding='utf8')
        syntax(tmp)
        os.replace(tmp, SERVICE)
        shutil.copy2(args.adapter_source, ADAPTER)
        syntax(SERVICE)
        syntax(ADAPTER)
    except Exception:
        SERVICE.write_bytes(orig)
        ADAPTER.unlink(missing_ok=True)
        raise
    print('BACKUP_PATH=' + str(folder))
    print('BACKEND_CROMA_PATCH=INSTALLED')
    print('AMAZON_FLIPKART_WORKER_UNCHANGED=YES')
    print('SCRAPEDO_USED=NO')

if __name__ == '__main__':
    try: main()
    except Exception as e:
        print('PATCH_ERROR=' + str(e)[:300], file=sys.stderr)
        sys.exit(1)
