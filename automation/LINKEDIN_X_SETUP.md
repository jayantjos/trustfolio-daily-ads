# TrustFolio LinkedIn + X crossposting (official APIs; independent of Meta)

## What it does

Workflow: `.github/workflows/linkedin-x-crosspost.yml`. Runs only after the **scheduled** TrustFolio Instagram+Facebook workflow completes successfully on `main`. It downloads that job's immutable approved QA artifact, preferring the final post-publication artifact when a last-minute website price/ranking change required re-rendering.

The LinkedIn post uses **the exact approved JPEG and Instagram campaign caption**. The X post uses the **same exact JPEG, category, budget, brand (where applicable), ad type and TrustFolio filtered landing URL**, with a shorter caption to meet X's character limit.

There are three distinct daily modes, not three additional variants: Budget, Budget+Brand, and Comparison. The source schedule remains 08:30, 13:30 and 19:00 IST, plus recovery windows. Each new network has one immutable date/mode lock, so **at most 3 LinkedIn and 3 X posts per IST day**. Delayed GitHub Actions runs can run later than their nominal start. A successful Meta run is not sufficient alone: the source artifact must match **both confirmed Meta publication ledger records**, have the original five correct ranked products, pass QA and latest price/rank parity, and serve an exact hosted JPEG.

**Neither new platform is enabled by default.** Instagram and Facebook posting, branding, product selection, Meta token and daily cap remain unchanged. No app, scraper, MongoDB or website edits. A reserved, potentially ambiguous API write is *never retried blindly*; reconciliation is necessary to avoid duplicates.

## Account setup required before actual posts

Use **GitHub repository Settings → Secrets and variables → Actions**, not chat. Never paste access tokens here, in a git file, or in logs.

### LinkedIn

1. Create or use a LinkedIn developer app with authorized `w_organization_social` (TrustFolio company page) or `w_member_social` (personal profile). Grant required app products and perform OAuth authorization.
2. Put the OAuth member **user access token** into the secret `TF_LINKEDIN_ACCESS_TOKEN`.
3. Set variable `TF_LINKEDIN_AUTHOR_URN` to the **actual authorized author**: `urn:li:organization:YOUR_ID` for the TrustFolio Company Page, or `urn:li:person:YOUR_ID` for an intended member account. Never invent an organization ID. Note that company-page posting may require approved product access and a page admin role.
4. Variable `TF_LINKEDIN_VERSION` defaults to `202608` (a documented version); check the supported API version during activation. Tokens can expire and may require renewal.
5. Verify the intended account and authorization with a controlled first post before setting `TF_LINKEDIN_DIRECT_PUBLISH_ENABLED=true`.

### X (Twitter)

1. Create an X developer project/app, enable appropriate **user-context OAuth 2.0** scopes for user identification, post creation and media uploads (e.g. `users.read`, `tweet.read`, `tweet.write`, `media.write` as supported by your app).
2. Set secret `TF_X_USER_ACCESS_TOKEN` (not app-only bearer token); set variable `TF_X_USER_ID` to your intended account's **real numeric user ID**. Every live attempt checks `GET /2/users/me` to prevent posting to the wrong account.
3. X's API can incur **per-operation charges**, especially posts containing links. Only after approving those costs set `TF_X_PAID_API_APPROVED=true`.
4. Only after the account and billing are verified set `TF_X_DIRECT_PUBLISH_ENABLED=true`. Keep it off until then. Renew OAuth tokens as needed.

### Safe test

GitHub Actions → **TrustFolio opt-in LinkedIn and X crossposting (isolated from Meta)** → Run workflow. Supply the ID of a completed Meta scheduled run from **today's IST date**. A `workflow_dispatch` **always** tests/prints the campaign ID, mode and X text length only; it cannot publish even if live flags are enabled.

Pull requests run eight offline API and duplication tests and cannot post. The official X route uses `/2/media/upload/initialize` → `/{media_id}/append` → `/{media_id}/finalize` → `/2/tweets`. LinkedIn uses Images API `initializeUpload` + authorized upload, followed by `/rest/posts`.

If the original Meta source remains unstable, unavailable, unverified, or credentials/permissions are missing, **no LinkedIn/X feed post is allowed**. A reserved external API attempt needs manual reconciliation rather than blind replay.

Official documentation:
- https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/images-api
- https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
- https://github.com/xdevplatform/docs/blob/main/x-api/posts/manage-tweets/introduction.mdx
