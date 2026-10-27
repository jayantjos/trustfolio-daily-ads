# TrustFolio $0 LinkedIn + X scheduling via Buffer Free

**Why Buffer Free?** Verified [Buffer pricing](https://buffer.com/pricing) and [Buffer's free API](https://support.buffer.com/en-us/articles/what-is-buffers-api-GtIYIQilz5): up to 3 connected social channels, 10 pending scheduled posts **per channel** (queue slots refill when they publish), 1 personal API key, 3,000 API requests per 30 days. [Supported platforms](https://support.buffer.com/articles/connecting-your-channels-to-buffer-HvWLgAJvL9) include both X and LinkedIn.

TrustFolio uses **two channels** in a Buffer Free account: one LinkedIn Page or profile, and one X profile. You do **not** have to attach Instagram or Facebook because their existing direct Meta publishing remains active and untouched.

## Connect just two channels

1. Create/sign in at **https://buffer.com**, choose the **Free ($0)** plan.
2. In Buffer → Channels, connect your **intended TrustFolio LinkedIn Company Page** (or personal profile) and **intended X (Twitter) profile**. You approve Buffer's platform OAuth prompts yourself.
3. Buffer → Account Settings → **API**: create a **personal API key**. Store only as GitHub Actions **repository secret** `TF_BUFFER_API_KEY`. **Never paste a key into chat or commit it**.
4. Retrieve channel IDs with the official [Buffer GraphQL channel query](https://developers.buffer.com/guides/data-model):
   - `query { account { organizations { id name } } }`
   - `query { channels(input: { organizationId: "YOUR_ORG_ID" }) { id name service } }`
   Choose the **real IDs** corresponding to your approved LinkedIn and X accounts, not other accounts. GitHub repository Actions **variables**: `TF_BUFFER_LINKEDIN_CHANNEL_ID`, `TF_BUFFER_X_CHANNEL_ID`.
5. Leave repository variable `TF_BUFFER_FREE_PUBLISH_ENABLED` **false** until all IDs have been securely verified against the intended accounts. Once validated, switch it to `true`. It can be switched back to `false` as an emergency OFF switch.
6. Keep **direct X paid API** flags `TF_X_DIRECT_PUBLISH_ENABLED=false` and `TF_LINKEDIN_DIRECT_PUBLISH_ENABLED=false`: Buffer Free is an **alternative**, not an additional source of duplicate posts.

## What happens after activation

Every successful *scheduled* Instagram + Facebook workflow triggers `.github/workflows/linkedin-x-crosspost.yml` to read the same FINAL image artifact and matching per-mode/day publication ledgers. It requires five real, correctly ranked and still-eligible products, price parity and exact publicly hosted JPEG. The Buffer GraphQL `createPost` API (not X's paid API) schedules the image and caption five minutes after that verification. The original Budget, Budget+Brand and Comparison date/mode rotation is preserved.

- **LinkedIn:** original approved image and campaign caption.
- **X:** original approved image; compact caption retaining product category, budget, brand where applicable, and exact filtered TrustFolio link.
- **Deduplication:** same locked `trustfolio-extra-social-ledger` per day, mode, and network used by the direct-API alternative. An ambiguous external API response is **never** blindly replayed.
- **Accounting:** GitHub records `buffer_api_accepted_scheduled`, not false claims that LinkedIn/X feeds have already published. The eventual delivery status is in Buffer's queue/Published tabs.
- **Free limits:** free plan gives 10 pending scheduled posts per connected channel. The intended schedule typically queues one per successful Meta campaign, not months ahead, so it stays within 10 when Buffer is delivering normally. If the queue fills, the operation fails closed and needs manual investigation.
- **Scheduling timing:** Meta source posts are at nominal 08:30, 13:30, 19:00 IST; recovery and GitHub cron delays can push them later. Buffer schedules each new cross-post five minutes after the completed verified Meta workflow rather than pretending it already published on either network.
- **Spending:** Buffer Free uses Buffer's social publishing integrations, so **no X developer API billing** is initiated through this route. Creating a paid Buffer subscription is **not** part of this integration.
- **Manual dry run:** GitHub Actions → `TrustFolio opt-in LinkedIn and X crossposting (isolated from Meta)` → Run workflow with a recent Meta run ID. This path **never** publishes, even if flags are enabled.

If your Buffer plan, connected channels or API key are not available, the new route remains OFF. Never use browser password scripts or unofficial posting automation as a workaround.
