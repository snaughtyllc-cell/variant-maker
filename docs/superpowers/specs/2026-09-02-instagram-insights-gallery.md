# Instagram Insights in Gallery (Track → Amplify)

**Date:** 2026-09-02  
**Status:** Design — parked until Jeff unparks a slice. This PR is the spec only.  
**Product name:** VaryForge  
**Jeff (2026-09-02):** Meta developer app → operator Connect Instagram → pull
Insights → Gallery shows the pack (300k views, ranked copies) → suggestions
(dead original vs winner) → mint more variants of winners. Same agency
testing loop, productized. Not “open Insights on every Reel.”

**Depends on:** `post_url` paste (`2026-08-20-post-url-tracking.md`), Gallery
source groups, `regenerate(source_id, n)`, Drive-style Jeff-once OAuth.
**North star:** `2026-08-20-butter-loop.md` F3 + F4.

## Verdict

Yes. This is the missing half of the product.

VaryForge already owns the hard part: unique files that look like originals.
Without a scoreboard on **those files**, operators still live in Instagram
Insights, one Reel at a time, then guess which original to clone. Butter
sells Post → Track → Amplify as glue. We already wrote that loop. What we
did not ship is **Track with real numbers on the pack**, because we refused
scraping and account proxies.

A Meta **developer app** is the allowed door. It is the same shape as
Connect Google: Jeff configures the app once; each workspace signs in as
**their** Instagram professional account; Studio pulls what Insights already
shows, then rolls it up by **source / pack / copy** — identity Instagram
does not have.

That join is the product. A generic IG analytics dashboard without variant
identity is just another Insights clone. Do not build that.

## What “game changer” means here (operator feel)

Five originals in Gallery, each with a pack of copies. After they post:

| They should see in Gallery | Not this |
|---|---|
| This **pack** did 312,400 views (sum of matched copies) | Open 20 Reels in the IG app |
| Copy v07 is 80% of that; v12 is dead | Spreadsheet of permalinks |
| **This original** is the million-view winner vs the other four | “v07 looks lucky” with no source grouping |
| Suggestion: mint 20 more of the winner (same Fast engine) | Overlays / hook scrambles |
| Suggestion: this original’s copies are all quiet — try a new source | A fake “flagged” stamp from views |

Auto-tracking is the default once an account is connected. Suggestions are
copy + one click first. Auto-generate more of a winner is a **workspace
toggle**, not day-one behavior.

## Two different truths (do not mash them)

| Signal | What it is | Where it lives | Who says so |
|---|---|---|---|
| **Policy / land** | Passed, duplicate-rejected, flagged | `platform_result` + Drops / Drop Ledger | Human oracle (VA marks it). Unlabeled = pass. |
| **Distribution / work** | Views, reach, likes, comments, shares, saved | Insights snapshot on the variant | Instagram, via official API |

A copy can **pass** (not taken down) and still get **zero push**. That is
exactly the agency read Jeff named. Insights do **not** expose “this was
flagged” or “this is shadowbanned.” Dead views are a **heuristic**, labeled
as potential, never as a detector verdict.

Phase 12 (`2026-08-18-platform-outcome-learning.md`) stays the policy-learning
track. This spec does not un-skip 12c. Do not feed view counts into the
uniqueness gate.

## Why official Meta, not a scraper

| Approach | Stance |
|---|---|
| **Instagram API with Instagram Login** (`graph.instagram.com`) | **This track.** Operator Connect. Professional (Business/Creator) accounts. |
| Facebook Login + Page-linked IG (`graph.facebook.com`) | Fallback only if Instagram Login cannot cover a client. More Page / BM dance. |
| Paste `post_url` only (v1, shipped) | Keep. Join key when they pasted. Open post still works with no Connect. |
| Public oEmbed / OG | Optional extra; fails on 18+ / restricted. Not the scoreboard. |
| Logged-in browser farm / Eagle / “UI remote” as the VA | **Out.** That is account-proxy. `CLAUDE.md` forbids it. |

“UI remote” in the pitch is **OAuth consent on Instagram**, same as Connect
Google — not Studio driving the Instagram app as someone else.

## Meta constraints (honest)

- **Professional accounts only.** Personal IG cannot grant Insights.
- **Jeff-once app.** Create the Meta app, add Instagram product, set
  redirect to Studio. Operators never create a Meta app (same rule as Drive /
  GCP).
- **App Review** for `instagram_business_basic` +
  `instagram_business_manage_insights` (Advanced Access). Until then: Meta
  test users / test IG accounts only — same pain as unverified Drive OAuth.
- **Tokens expire.** Store and refresh long-lived user tokens per connected
  IG user. Disconnect deletes the file.
- **Metric name:** use **`views`** (replaces deprecated `impressions` /
  `plays` / `video_views` on current Graph versions). Reach +
  likes/comments/shares/saved stay useful. If `views` errors on a given
  login type, fail that metric honestly; do not silently substitute a dead
  field.
- **Delay.** Insights lag. Do not scream “not getting pushed” at T+20
  minutes. Suggestions need a floor (see G4).
- **No “flagged” field.** Never invent one from the API.

## Identity (the join)

We are still not the poster. Repurpose / the phone / a VA publishes. After
Connect, the media **appears on the connected professional account**. Match
that media to a variant.

Stable keys, in order:

1. **`ig_media_id`** once matched (survives caption edits).
2. **Normalized permalink** ↔ `post_url` (v1 paste, or auto-filled from
   `permalink` on the media object).
3. **`job_id` + `source_id` + variant index** — Studio identity. Never the
   Drive display name (Repurpose rename).

Do **not** auto-guess by caption text or “posted around the same time.”
Unmatched recent Reels get a **picker** on the pack (“this IG post is this
copy”). Exact permalink match may fill `post_url` for them.

`drop_url` stays Drive file id. `post_url` stays live permalink. Insights
hang off the variant next to those, not on the ledger as a second truth.

## Where it shows (no new tab)

Studio IA stays: Studio · Gallery · Drops · Workflows · Drive.

| Surface | What to add |
|---|---|
| **Drive** (or a card on that page) | Connect Instagram / connected @handle / Disconnect. Jeff-once env, not a phone tab. |
| **Gallery pack header** | Total views for matched copies. “12 of 20 linked.” Winner / quiet suggestion line. |
| **Gallery tile** | Compact views (and a dead/quiet mark only after G4 floors). Existing uniqueness + Flagged chips stay. |
| **Variant sheet** | Views / reach / engagement + last synced. Keep paste + Passed/Duplicate/Flagged. |
| **Drops** | Optional pack-level views once G3 exists. Drops is still the policy board (unlabeled = pass). |

Watch is not a tab. Insights is not a tab.

## Amplify (winners → more unique files)

The engine already has `JobStore.regenerate(source_id, n)` (Gallery
shortfall / “add copies”). Amplify is that button with a **source chosen by
Insights**, not a new renderer.

- Same Fast (or the job’s quality mode), same uniqueness gate, new seeds.
- **Unit of winning is the source** (the original), not a lucky copy. We
  mint more variants of the original that is working — agency practice.
- Do **not** clone the winning copy’s exact filtergraph. New samples.
- Do **not** amplify a source whose copies are all quiet. That is the
  “try a new original” suggestion.

Auto-amplify (G5): workspace setting, max packs per day, never while a job
is running for that source, never from unmatched (0 linked posts).

## Suggested slices (when we build)

### G0 — this spec (done in this PR)

No code. Cross-links from butter-loop F4, post-url v3, after-sales, IA.

### G1 — Connect Instagram (workspace OAuth)

Mirror Drive: Settings → Drive (or adjacent card) → **Connect Instagram**
→ Instagram Login consent → callback stores token at
`{workspace}/instagram/oauth_<ig_user_id>.json` → status shows @handle.

Env (Jeff / Railway, not operators):

- `VARIANT_IG_APP_ID`
- `VARIANT_IG_APP_SECRET`
- `VARIANT_IG_REDIRECT_URI` (default
  `https://<studio-host>/api/instagram/oauth/callback`)

**Box:** new `variant_maker/server/instagram_oauth.py` + routes in `app.py`
(oauth start/callback/status/disconnect only), Drive-page card,
server tests with a fake token file. **Not:** sampler, uniqueness, posting.

Permissions: `instagram_business_basic`,
`instagram_business_manage_insights`. No `instagram_content_publish`.

### G2 — Sync insights onto linked variants

- `GET /{ig-user-id}/media` (permalink, timestamp, media product type)
- `GET /{ig-media-id}/insights?metric=views,reach,likes,comments,shares,saved`
  (request only metrics valid for that media type; skip missing)
- Match permalink → `post_url` / store `ig_media_id`
- Persist snapshot on the variant (`job.json`): counts + `fetched_at`
- Refresh: on Gallery load (rate-limit) + a manual **Sync insights**
- No Redis. No always-on queue. Same “poll when they look” pattern as
  other Studio status.

**Box:** `instagram_insights.py`, variant fields, `POST /api/instagram/sync`,
tests with recorded JSON fixtures (no live Graph in CI).

### G3 — Gallery rollup

Pack header: **Σ views** of matched copies, linked count. Tile: views.
Sheet: full snapshot. Pure helpers for sum/rank so the UI is testable
without Graph.

Copy examples (lock in tests):

- `312.4k views across 14 posts`
- `3 live posts` stays the paste chip until views exist
- Unlinked copies do not count as zero — they count as **unknown**

### G4 — Suggestions (copy + button, no auto job)

Pure function on a pack + account recent medians. Examples:

- **Winner:** this source’s matched views ≥ 3× median of other sources
  (same workspace, last 7 days) **and** min floor (e.g. 10k views, tune
  from Jeff’s accounts). Button: **Generate 20 more of this original**.
- **Quiet original:** ≥ N copies linked, age ≥ 24h, **all** matched views
  below a quiet floor **and** the same account’s other recent media is
  not quiet. Copy: *These copies are not getting push. Try a new original
  — this may be the video, not the variant.* Never say “flagged.”
- **One dead copy among live siblings:** *This copy is quiet vs the rest of
  the pack.* Optional: mark Flagged stays a **human** action.

No uniqueness / VMAF / look change.

### G5 — Auto-amplify (later)

Workspace toggle off by default. If on: enqueue `regenerate` for G4
winners only, cap per day, skip in-flight sources. Still Fast uniqueness.
Still not a detector.

## Non-goals

- Native Instagram / TikTok / Shorts posting.
- Logging into Instagram as the VA; device farms; UI automation.
- A local “will this get flagged / pushed” model.
- Raising the 24-bit Fast gate because a winner “needs more uniqueness.”
- Pixel-AI / overlay scramble of the winning file.
- TikTok / YouTube analytics in G1–G4 (IG first; other platforms are a
  later Connect, same join on `post_url`).
- Putting tokens or Graph calls in the **CLI** FFmpeg path. This is Studio.
- Redis, Postgres, public Meta app for random signups. Invite-only Studio
  + test users until App Review.

## Invariants

- Color, zero-mean, VMAF, audio sync, 24-bit Fast gate unchanged.
- `platform_result` remains the policy oracle. Insights never write
  `flagged` / `duplicate_reject`.
- Unlabeled policy still = pass.
- Unmatched Insights media must not attach to the wrong variant.
- Lab vs Live: implement on Lab, promote Studio files with
  `scripts/promote-to-live.sh`. Do not git merge Lab ↔ Live.

## Success

An agency opens Gallery, not Instagram Insights, to answer: **which
original is working, which copies are carrying it, should we mint more or
shoot something else.** Connect once per professional account. Numbers
update without a spreadsheet. Generate-more on a winner is the same Fast
pack they already trust.

## Frozen

24-bit Fast gate, VMAF on, Fast = CPU, HQ = GPU, unlabeled = pass,
invite-only, no Pixel-AI overlays, no account-proxy posting, no CLI Graph.
