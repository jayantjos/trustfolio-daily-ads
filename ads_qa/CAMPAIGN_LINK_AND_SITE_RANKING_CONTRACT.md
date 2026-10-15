# TrustFolio campaign landing and ranking verification contract

## Source of truth

Advertising images may use any products from the daily payload, but **the claim that the
ad Top 5 equals the website Top 5 cannot be made until the site returns the same
product IDs in the same rank order** for the same query. The current ads selection
engine independently ranks MongoDB products and may not match the website sorter.

For each budget or brand campaign, fetch a snapshot directly from the website's
actual recommendation endpoint, preserving its ordering (do not synthesize a
snapshot by copying products out of the ad). The endpoint and its authentication
must first be resolved from the site/backend source. Keep network/API credentials
out of the repository.

A ranking snapshot must supply:

```json
{
  "category": "smartwatches",
  "budget_inr": 2000,
  "brand": "",
  "products": [
    {"rank": 1, "product_id": "real-site-id-1"},
    {"rank": 2, "product_id": "real-site-id-2"},
    {"rank": 3, "product_id": "real-site-id-3"},
    {"rank": 4, "product_id": "real-site-id-4"},
    {"rank": 5, "product_id": "real-site-id-5"}
  ]
}
```

Only site-sourced snapshots qualify. `check_ranked_site_snapshot(ad, snapshot)`
returns validation problems; missing snapshots **fail closed**. A brand recommendation
also requires each product's actual brand and a strict budget ceiling.

## Category / brand / budget link

`campaign_link(ad, config, ad_id)` generates a category URL with UTM tracking.
The original safe landing URL remains unchanged until the frontend verifies query
prefills. It returns `requested_filters`, `prefill_ready`,
`unverified_prefill_fields`, and `site_ranking_status=unverified`.

The frontend needs to implement, and an end-to-end browser test must prove:

1. `/category/<slug>/?budget=2000` selects the category and populates the budget
   input, and results actually use this budget (not just display the number).
2. `/category/<slug>/?budget=2000&brand=<encoded-brand>` additionally selects
   the brand, including spaces/ampersands, and uses the same ranking logic as the
   on-page Search button.
3. Page reload and mobile navigation retain the selected filters.
4. Unknown categories/brands fail safely; source product IDs and ordered results
   can be queried for server-side parity.
5. An Android app link must be tested for the same filters before it is used.
   The generic Play Store URL is not a prefilled product search deep link.

After a browser/API test passes, set BOTH `enabled: true` and
`frontend_verified: true` for each filter in the deployed link config, e.g.:

```json
"budget_query_parameter": {
  "enabled": true, "frontend_verified": true, "parameter": "budget"
},
"brand_query_parameter": {
  "enabled": true, "frontend_verified": true, "parameter": "brand"
}
```

Do not enable these flags just to silence a QA failure. The site frontend code
is not present in this ads repository, so this branch **does not claim the
actual website filters are ready**.

## Social posting

- Facebook and paid social posts can carry a genuine destination URL/CTA.
- Regular Instagram feed caption URLs are not tappable. Use a verified bio link,
  Story link sticker, or supported ad CTA. Make sure a bio link targets the
  correct campaign before claiming that it is prefilled.
- Real-time price and catalog changes may change rankings after posting; retain
  `generated_at` and warn that prices can change. Before scheduling/publishing
  automatically, revalidate the landing route, filter behavior, ranking parity,
  media URL, and authorized social account.
- Never publish to a personal account when the requested brand is @trustfolio3.
- Approval of the visual template alone does not constitute approval of claims,
  price accuracy, landing behavior, or account publication permissions.
