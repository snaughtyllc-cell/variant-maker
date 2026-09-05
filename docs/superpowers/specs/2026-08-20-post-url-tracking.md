# Paste live post links (tracking without posting)

**Date:** 2026-08-20  
**Status:** v1 in Studio — paste + open; no scrape  
**Product name:** VaryForge

Studio does not post. VAs (or Repurpose) post from Drive / the phone, then
**paste the live permalink** onto the variant. That URL is how we track the
clip for views / CPM later without logging into Instagram from Studio.

## Why this, not a scraper

Tracking is hard because **we are not the poster**. Butter posts for you;
we generate unique files. The cheap glue is: after a post exists, copy the
link back into Gallery.

| Approach | When | Why / why not |
|---|---|---|
| **v1 Paste permalink** | Now | VA copies IG/TikTok/Shorts URL into the variant sheet. Click to open. No login, no scrape. |
| **v2 Public metadata** | Later, optional | oEmbed / OG on *public* posts only. Age-gated / 18+ accounts will fail without a session. |
| **v3 Official APIs** | Building — Analytics tab spec | Real views on accounts the workspace **Connected**. Instagram Login, not a scraper. Analytics scoreboard + Gallery compact views + amplify. `docs/superpowers/specs/2026-09-02-instagram-insights-gallery.md`. |
| **Logged-in browser farm** (Eagle, etc.) | Parked forever for this product | Sees only what a logged-in profile sees. Restricted 18+ needs that session. Out of scope: no account proxies (`CLAUDE.md`). Trial-and-error, not a product loop. |

`drop_url` on the Drop Ledger is the **Drive file id**. `post_url` is the
**live post**. Do not overload them.

## v1 operator loop

1. Generate Fast → Share/Save or Send to Drive.
2. VA / Repurpose posts.
3. Open the variant in Gallery → **Live post link** → paste → Save.
4. **Open post** stays in Studio so they do not hunt the URL again.
5. Passed / Duplicate / Flagged stay the platform-oracle labels.

Unlabeled `platform_result` is still pass. A missing `post_url` just means
“not pasted yet,” not a miss.

## Box

- `POST /api/variants/{source_id}/{index}/post-url` `{ "url": "https://…" }`
- Empty URL clears. Persist in `job.json` + `manifest.json` + ledger `post_url`.
- Gallery variant sheet paste field; tile shows a **link** chip.

## Frozen

No Instagram login from Studio. No Eagle runner. No uniqueness / VMAF change.
No native posting.
