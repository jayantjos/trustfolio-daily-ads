#!/usr/bin/env python3
"""Read-only, sanitized discovery of TrustFolio website search and ranking contracts.

Executed over verified SSH from GitHub Actions; no application writes, deploys,
database calls, or raw source copies. Only small selected lines are emitted.
"""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path.home() / "apps" / "trustfolio"
FILES = {
    "web/category_entry": ("trustfolio-main", "src/app/category/[slug]/page.tsx"),
    "web/category_products": ("trustfolio-main", "src/app/category/[slug]/products/page.tsx"),
    "web/budget_filter": ("trustfolio-main", "src/components/BudgetFilter.tsx"),
    "web/brand_selector": ("trustfolio-main", "src/components/BrandSelector.tsx"),
    "web/products_table": ("trustfolio-main", "src/components/ProductsTable.tsx"),
    "web/api": ("trustfolio-main", "src/services/api.service.ts"),
    "web/ranking": ("trustfolio-main", "src/utils/productRanking.ts"),
    "web/home": ("trustfolio-main", "src/app/page.tsx"),
    "backend/routes": ("node-backend", "routes/index.js"),
    "backend/product_controller": ("node-backend", "controllers/ProductController.js"),
    "backend/recommendation": ("node-backend", "services/ProductRecommendationService.js"),
    "backend/brand_service": ("node-backend", "services/BrandService.js"),
    "backend/category_service": ("node-backend", "services/CategoryService.js"),
    "backend/slug_utils": ("node-backend", "utils/categorySlugUtils.js"),
    "backend/category_controller": ("node-backend", "controllers/CategoryController.js"),
}
PATTERN = re.compile(
    r"(?:searchParams|useSearchParams|router\.|\.push\(|URLSearchParams|"
    r"budget|brand|rank|sort|category|slug|search|product|endpoint|"
    r"fetch\(|axios\.|\.get\(|export\s+(?:default|function|const)|"
    r"router\.(?:get|post)|req\.(?:params|query)|pageSize|limit|score|rating)",
    re.IGNORECASE,
)
SENSITIVE = re.compile(
    r"(?:api.?key|secret|token|password|credential|process\.env|auth|"
    r"bearer|cookie|mongodb|mongoose|razorpay|private.?key|"
    r"username|connectionstring|database_uri|firebase.?admin|"
    r"access.?key|^\s*//.*https?://[^\s]+\?.*=)",
    re.IGNORECASE,
)
SECRETLINES = re.compile(
    r"(?:-----BEGIN |(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{18,}|"
    r"mongodb(?:\+srv)?://|AIza[0-9A-Za-z_-]{20,})"
)

result = {}
for label, (app, subpath) in FILES.items():
    file = ROOT / app / subpath
    if not file.is_file() or file.is_symlink():
        result[label] = {"missing": True}
        continue
    raw = file.read_bytes()
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        result[label] = {"error": "not_utf8"}
        continue
    picked = []
    for number, line in enumerate(lines, 1):
        if len(picked) >= 72:
            break
        if not PATTERN.search(line) or SENSITIVE.search(line) or SECRETLINES.search(line):
            continue
        # Strip comments and JSX text noise where possible; do not emit URLs.
        clean = re.sub(r"https?://[^\s'\x22\\)]+", "<URL>", line.strip())
        if not clean or len(clean) > 200:
            continue
        picked.append({"line": number, "text": clean})
    result[label] = {
        "source_path": f"{app}/{subpath}",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "total_lines": len(lines),
        "matched": picked,
    }
print("READONLY_SITE_CONTRACT_DISCOVERY_BEGIN")
print(json.dumps(result, indent=2, ensure_ascii=False))
print("READONLY_SITE_CONTRACT_DISCOVERY_END")
