#!/usr/bin/env python3
"""Guarded, idempotent Croma LIVE-check UI update (not a fake LIVE badge)."""
import argparse
from pathlib import Path
import sys

REPLACEMENTS = {
    "src/components/ProductsTable.tsx": [
        ("const canBeLive = platform === 'amazon' || platform === 'flipkart';",
         "const canBeLive = platform === 'amazon' || platform === 'flipkart' || platform === 'croma';"),
        ("// Live Amazon / Flipkart prices: stored price renders first, live one replaces it ~1-2s later.",
         "// Live Amazon, Flipkart and Croma prices: stored price renders first, verified live replaces it."),
    ],
    "src/services/api.service.ts": [
        ("Live Amazon / Flipkart prices for the listings on screen", 
         "Live Amazon / Flipkart / Croma prices for the listings on screen")
    ],
    "src/types/product.ts": [
        ("false = no live source for this listing (Croma, search-only link)",
         "false = no verified live source for this listing"),
        ("    in_stock: boolean;", "    in_stock: boolean | null;")
    ]
}

def patch(root, apply):
    updated=[]
    for rel, replacements in REPLACEMENTS.items():
        p = root / rel
        if not p.is_file():
            raise RuntimeError(f'missing {rel}')
        value = p.read_text('utf-8')
        nextval=value
        for old, new in replacements:
            if nextval.count(new) == 1 and nextval.count(old)==0:
                continue  # already changed
            if nextval.count(old) != 1 or nextval.count(new) != 0:
                raise RuntimeError(f'unsafe anchor in {rel}: {old[:70]}')
            nextval=nextval.replace(old,new,1)
        if nextval != value: updated.append((p,nextval))
    print('CROMA_FRONTEND_PATCH_ANCHORS=PASS')
    print('FRONTEND_FILES_TO_CHANGE='+str(len(updated)))
    if apply:
        for p, v in updated: p.write_text(v,'utf-8')
        print('CROMA_CHECKING_INDICATOR_PATCH=INSTALLED')
    else:
        print('CROMA_FRONTEND_PATCH_DRY_RUN=PASS')

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    try:patch(args.root.resolve(),args.apply)
    except Exception as e:print('FRONTEND_PATCH_ERROR='+str(e)[:200],file=sys.stderr);sys.exit(1)
