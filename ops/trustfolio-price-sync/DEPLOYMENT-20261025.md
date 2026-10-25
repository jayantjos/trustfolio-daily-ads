# TrustFolio MongoDB live price sync — production verification

Executed October 25, 2026 on the TrustFolio VPS via a temporary GitHub Actions deployment job.

- Backup directory: `/home/scraperuser/backups/trustfolio-price-sync/20261025T011428Z`
- Installed files: patched backend LivePriceService.js, CategoryService.js, ProductController.js; new scripts/trustfolio-category-price-watcher.js.
- Runner syntax/unit checks: passed.
- Backend patch syntax: passed.
- PM2: trustfolio-backend, trustfolio-web, trustfolio-admin and trustfolio-price-watcher: online.
- MongoDB change stream: active for `my_products`.
- Initial category refresh: 20 categories, 0 failures.
- API `/api/categories`: HTTP 200.
- Catalog watcher calls no marketplace price APIs.

Availability policy: confirmed out-of-stock, sold out or discontinued listings are archived to `my_products_deleted` before deletion. Ambiguous unavailable/N/A requires two checks. A transient timeout or worker error does not trigger deletion.

Known limitations: no real live marketplace request was forced for QA (to avoid API charges); direct update-to-range integration under production mutation was not tested. In-memory API caches for external changes may last until their TTL. Existing legacy scraper crons were not modified or verified.

Deployment patcher and watcher source are retained in this folder.
