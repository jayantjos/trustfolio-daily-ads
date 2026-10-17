# Direct official Meta publishing (no Metricool paid API)

This is the long-term **VPS render → GitHub QA → Instagram + Facebook** route.
It uses Meta's official Graph API and publishes from the account owner's
authorized app credentials. It **never scrapes Meta**, buys followers, or
modifies `~/apps/trustfolio` or the TrustFolio scraper.

## Current status / strict activation rules

**Integration code is ready to test without credentials; live Meta publishing
defaults OFF.** It must only be enabled after the owner completes official
Meta OAuth/token authorization and we verify first real read-only preflight.
An existing connection to Meta via Metricool DOES NOT authorize GitHub's
Meta API integration and does not expose a reusable access token.

The GitHub runner first builds a real website Top-5 ad on the existing ads
VPS (`~/new_scraper/ads`), compares exact product IDs and rank positions,
ensures no image overlap, writes a full-sized original 1024x1536 PNG and
uncropped 1080x1350 JPEG, uploads a private GitHub artifact, and verifies
the public JPEG's exact bytes at `media.trustfolio.in`. THEN the direct
Meta step may run if and only if explicitly enabled.

A second legacy Metricool step exists in the workflow. Never enable both:
the code refuses to run when `TF_AUTO_POST_ENABLED=true`.

## Required one-time Meta authorization

1. At `https://developers.facebook.com/apps/`, use the TrustFolio-owned
   Meta developer account to create/configure an app with Instagram
   publishing through **Instagram API with Facebook Login**.
2. Confirm the **Facebook Page** is under the owner’s administrative
   control and that Instagram `@trustfolio3` is a **Professional** (Business
   or Creator) account linked to that *same Page*. The connected Metricool
   app showed Facebook Page ID `619193294620746`; this identity is pinned
   but must still be verified directly against Meta before any posting.
3. Grant only the required relevant permissions for content publishing.
   For the Facebook Login Instagram flow Meta lists `pages_show_list`,
   `pages_read_engagement`, `instagram_basic`, and
   `instagram_content_publish`; for Facebook Page photos add
   `pages_manage_posts`. Additional API/app review or Advanced Access
   may be required depending on app type/role and visibility.
4. Use the official Graph API Explorer / Access Token tool to obtain the
   **Page access token** for the correct Page (consider renewal and secure
   long-lived or authorized system-user token where supported).
   Never send the token into a chat, public issue, screenshot or repo file.
5. Add GitHub repository **Actions secret**:
   `TF_META_PAGE_ACCESS_TOKEN` = Page access token.
   Protect secrets from untrusted PRs. Rotate token if compromised.
   GitHub built-in `GITHUB_TOKEN` already provides the ledger write scope.
6. Optional GitHub Actions variables (under Settings → Secrets and
   variables → Actions → Variables):
   - `TF_META_PAGE_ID=619193294620746` (must match verified Page)
   - `TF_META_POST_NETWORKS=instagram,facebook`
   - `TF_META_MAX_POSTS_PER_DAY_PER_NETWORK=2` (safe rollout limit;
      may be increased after successful tests and reach/quality review)
   - `TF_META_GRAPH_VERSION=v25.0` (pin/update to a supported version)
   - `TF_META_START_DATE=2026-10-26` (do not duplicate existing
      October 17–25 Metricool queued campaign posts)
7. Perform a **read-only identity and media test** before any new live
   posts. Only after verifying API permissions, Instagram username, Page
   ID, URL/file integrity and publishing quota set:
   `TF_META_DIRECT_PUBLISH_ENABLED=true`.
   Leave `TF_AUTO_POST_ENABLED=false`.
   The GitHub UI workflow_dispatch publish control also requires the
   global flag and credentials. A push/PR never publishes.

## Meta API calls (owner-authorized only)

- `GET /{PAGE_ID}?fields=id,name,instagram_business_account`
- `GET /{IG_USER_ID}?fields=id,username` checks exact `@trustfolio3`
- `GET /{IG_USER_ID}/content_publishing_limit` obtains account-specific
  rolling 24-hour `quota_usage` and `quota_total`. Published Meta docs
  differ on nominal numeric caps; **never hardcode an absolute IG quota**.
- `POST /{IG_USER_ID}/media` with verified public JPEG image_url/caption
- `GET /{CONTAINER_ID}?fields=status_code` until `FINISHED`
- `POST /{IG_USER_ID}/media_publish` with approved container ID
- `POST /{PAGE_ID}/photos` with public image URL and Facebook caption.

Meta can still auto-classify content or apply AI-related labels when its
policies require; using Python compositing alone does NOT prove source
artwork has no generative-AI history. Do not make false AI-free claims.
Instagram feed caption URLs are not tappable. Profile bio link hub:
`https://media.trustfolio.in/trustfolio-links/index.html`. Facebook post
URLs can be clickable.

## Duplicates, quotas, rollout and failure recovery

`trustfolio-meta-publishing-ledger` stores **one reservation per
(date, network, deterministic campaign ID)**. The GitHub content-create
request with no SHA is an atomic one-time reservation. The reservation
is retained on API failure/timeout, because a POST might already have
published; do not blindly resubmit. A human must inspect both networks
and the ledger before choosing a manual repair.

The workflow's concurrency group is shared with the old cron workflow to
avoid overlapping publisher invocations. Daily per-network cap defaults
to **2**; Instagram's own publishing limit is polled live. Platform
anti-spam and content quality policies may impose additional restrictions,
so larger volumes are never guaranteed.

The first migration date is **2026-10-26**, because Metricool previously
scheduled TrustFolio ads through October 25. Check those scheduled posts
before enabling, and move the start date later if necessary.

Daily 20-category rotation and three price tiers are configured under
`automation/campaigns.json`. Current cron cadence is 3 QA-verified creative
**candidates per day** (budget, brand+budget, five-product comparison),
not all 20 categories every day. The direct Meta publisher replaces the
distribution stage; scaling rendering to 20/day or more requires separate
batch/queue and publishing capacity checks. Free Meta publishing does
not mean unlimited or guaranteed posting.

## Official documentation

- Meta Instagram API with Facebook Login and media publishing:
  https://www.postman.com/meta/instagram/folder/u4g5a2a/instagram-api-with-facebook-login
- Meta Instagram Graph publishing:
  https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/content-publishing
- Meta Page posts:
  https://developers.facebook.com/docs/pages-api/posts/

Do not ask the user to run ad-server commands or paste access tokens.
