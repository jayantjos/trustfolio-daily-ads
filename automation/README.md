# TrustFolio automated social campaigns (website/apps remain untouched)

## Current scope: Instagram `@trustfolio3` only

The connected Metricool brand has blog ID `7271681`, user ID `5635852`,
Instagram `trustfolio3`, and timezone `Asia/Calcutta` as verified through
the connected Metricool account. The **brand label** is historical and not
used as a publication target. Automation must NEVER send to `@joshierjayant`.

Workflow: `.github/workflows/auto-instagram-campaigns.yml`

| UTC cron | IST schedule | Type |
|---|---|---|
| 03:00 | 08:30 | Budget/Top-5 |
| 08:00 | 13:30 | Brand + budget |
| 13:30 | 19:00 | Top-5 comparison |

GitHub cron runs can start late. Metricool will schedule the post for 20
minutes after successful verification, not retroactively for the nominal
cron hour.

1. Read `automation/campaigns.json`; deterministically rotate candidates
   by IST date. If no candidate has **five valid products from the actual
   TrustFolio website API**, produce a skipped manifest and DO NOT publish.
2. Render using the already deployed `ads_qa/render_site_ranked_qa_v1.py`
   in `~/new_scraper/ads`. Product mapping is rank 1 center, 2 left,
   3 right, 4 bottom-left, 5 bottom-right. The ads pipeline does not
   import or modify `~/apps/trustfolio`.
3. Verify actual source product IDs, URL category/budget/brand, 1024x1536,
   source provenance, zero geometry errors, and HTML V4 premium template.
4. Produce 1080x1350 JPG without trimming the approved design, caption,
   report, original PNG, and `post.json`.
5. Upload complete output as a GitHub Actions artifact (private, 30-day
   retention). These private artifacts are NOT public media URLs.
6. Copy only the approved JPG to `~/public_media/trustfolio-auto/` on the VPS
   (NOT `~/apps/trustfolio`). Verify a public HTTPS GET returns the exact
   same image bytes from `https://media.trustfolio.in/trustfolio-auto/`.
7. Only if explicitly enabled, publish to Metricool after REST API preflight
   validates the exact `trustfolio3` Instagram account, an attached image
   `mediaId`, and a GitHub ledger-based duplicate lock.

### Enable unattended Metricool posting

1. The connected ChatGPT Metricool app does NOT automatically grant GitHub
   Actions the Metricool API token. Metricool's REST API is available on
   **Advanced/Custom** plans; verify plan/API access first.
2. In GitHub repository Settings → Secrets and variables → Actions, add a
   **repository secret** called `TF_METRICOOL_API_TOKEN`. Obtain it in
   Metricool → Account Settings → API. Never commit or paste it into chat.
3. Optional GitHub variables `TF_METRICOOL_BLOG_ID=7271681` and
   `TF_METRICOOL_USER_ID=5635852` are pinned to the connected account;
   their defaults are already configured as fallbacks in the workflow.
4. Confirm that `media.trustfolio.in` serves the files under
   `/home/scraperuser/public_media/trustfolio-auto/` with valid HTTPS.
   Public URL is NOT assumed to exist just because a local file exists.
5. Inspect one completed manual/CI run and its public media URL. Only then
   set GitHub Actions variable `TF_AUTO_POST_ENABLED=true`.
6. Before this variable is true, cron runs only generate QA artifacts and
   media previews, never create a Metricool post. Manual dispatch defaults
   to `publish=false` even if the global flag is true.

### Publication audit and recovery

- `trustfolio-publishing-ledger` branch stores one atomic reservation per
  deterministic date/mode/category/budget/brand combination and the
  Metricool scheduling result. Do not casually erase reservations.
- If network times out after submitting to Metricool, the reservation
  remains and prevents duplicate posts. Verify Planner status before
  manually clearing a reservation.
- `status=scheduled` means scheduled, NOT confirmed published. Publication
  reporting should inspect Metricool after the target time.
- Link in an ordinary Instagram caption is **not tappable**. The caption
  includes a copyable verified filtered results URL; use a manually
  configured bio link for tappable navigation. Instagram Story link
  stickers are not API autopublished.
- Real website prices/ranks may change after generation. Never claim a
  permanent rank/price; all images are snapshots.

### Comparison campaign meaning

Until scraper consistency is fixed, `comparison` safely compares five
**different website-ranked products** from the same category/budget. This is
not same-model Amazon-vs-Flipkart-vs-Croma price comparison; that requires
a separate verified cross-retailer identity test and is not auto-posted.

### Later phases (not activated here)

1. Connect and test Facebook business page in Metricool and add its explicit
   platform-specific caption/visual QA.
2. Connect X/Twitter and verify text/media requirements. Do not send the
   Instagram caption blindly.
3. After static ads succeed, implement video/reel rendering and QA.
4. Only after social/video works, address scraper price/spec extraction.
   **Never edit `~/apps/trustfolio` or the original scraper as part of
   this workflow.**


### Clickable Instagram bio page (website + Google Play)

The verified public landing page is:

- `https://media.trustfolio.in/trustfolio-links/index.html`
- Example campaign: `https://media.trustfolio.in/trustfolio-links/index.html?category=headphones-earbuds&budget=3000`
- Brand example: `https://media.trustfolio.in/trustfolio-links/index.html?category=headphones-earbuds&budget=3000&brand=boAt`

It displays a comparison CTA to the verified TrustFolio budget/brand URL
and a clickable Android install CTA to the official Google Play app,
plus shortcut links for popular category budgets. The static HTML is
maintained in `automation/linkhub/index.html` and deployed read-only into
`~/public_media/trustfolio-links/index.html`, NEVER into `~/apps/trustfolio`.

**Instagram profile links cannot be changed via the connected Metricool
plugin or GitHub Actions.** Account owner must perform this one-time
`@trustfolio3 → Edit profile → Links → Add external link` action with the
stable base URL above, then test that both CTA buttons open correctly. A
copyable hub URL is automatically included in future campaign captions.

### AI-content disclosure: do not guess

Past posts were created with the Metricool `instagramData.isAiGenerated=true`
setting, which can cause the visible "AI content" label. That publishing
flag was chosen manually and **not inferred from Python/HTML rendering**.
The approved reference/master artwork used by the renderer may have its own
AI-generation history, which is currently unverified. Server-side
composition alone cannot establish a creative is entirely non-AI.

`automation/ai_provenance.json` is the source of truth. Until the original
artwork's source is independently verified, `master_artwork_origin=unknown`
and automated Metricool posts must disclose the AI flag. Only after the
creator reviews and confirms that reference/background/artwork was manually
designed without generative AI should `master_artwork_origin` be set to
`human_designed_no_generative_ai` and
`human_origin_verified=true`. PR QA guards that decision.

Published Instagram posts are not editable through Metricool's
`updateScheduledPost` connector (which supports only future scheduled
posts). Do not claim that an existing platform-managed label has been removed.


## Twenty-category rotating budgets (October 2026)

`automation/campaigns.json` now contains the canonical **20-category** catalogue
from the premium renderer, including each category's verified website-route
candidate, three INR budget tiers, and *candidate* brands. Nothing in these
lists asserts stock or brand availability. A live website Top-5 check is
mandatory before an ad qualifies.

Three GitHub cron slots are currently configured at 08:30, 13:30 and
19:00 IST for budget, brand+budget and five-different-products comparison.
They start from **different category offsets**, selecting one category
per slot (with bounded fallback to the next valid category) and rotate to
the next price tier when a category comes around again about 20 days later.
Under normal conditions this results in **3 rendered campaign previews/day**,
NOT 20 or 60 Instagram publications/day. GitHub cron can run late and QA
errors can cause an eligible campaign to be skipped.

The renderer bug from GitHub scheduled run `39030118311` is fixed:
the selected `mode` is now passed to `ads_qa.render_site_ranked_qa_v1.run`.
Previously brand and comparison runs were mistakenly sent as budget and
could fail with `Only brand-budget campaigns may contain a brand filter`.
The post QA gate also verifies reported campaign mode.

### Publication capacity and plan choices

**Publishing remains disabled** unless `TF_AUTO_POST_ENABLED=true`, the
correct Instagram target is confirmed, and a working Metricool Advanced/Custom
API token is added securely in GitHub Secrets. The ChatGPT-connected Metricool
MCP connector is separate from GitHub Actions and cannot be assumed to
authorize unattended GitHub-to-Metricool publishing.

Metricool Free includes **20 actually published posts per calendar month
total across connected networks**; each separately published Instagram
and Facebook post counts. Scheduling posts beyond this quota does not
increase the number that will successfully publish. Current official
plan documentation:
https://help.metricool.com/main-differences-between-free-and-paid-plans-bl0v9

Metricool Starter enables unlimited planner publishing subject to fair use,
plus LinkedIn, but its REST API does not support GitHub cron posting.
Metricool Advanced/Custom provides API access. X/Twitter may require
a separate plan add-on. YouTube standard uploads require video; static
Instagram posters are not automatically YouTube videos.

If the owner requests one new post for **each of 20 categories every day**,
that is at least 20/day/network; three modes for all 20 is 60/day/network.
Cross-publishing to Instagram and Facebook doubles the count. Do not
enable that volume as an assumed default: first verify the subscribed
plan, platform permissions, audience fit and publisher quotas.

The current default is category rotation with three daily QA renders,
not unattended publication and not guaranteed coverage if the website
lacks five genuine items. The remaining pre-scheduled October 17–25
Metricool posts must not be duplicated by an unattended job.

No code or data under `~/apps/trustfolio`, original scraper, or
existing published posts is modified by this change.
