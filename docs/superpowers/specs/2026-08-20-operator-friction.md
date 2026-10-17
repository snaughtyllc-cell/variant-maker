# Operator friction — Drive trust, phone save, tracking

**Date:** 2026-08-20  
**Status:** Active — Diagnostics hide and phone Save/Share videos ship with Studio; Drive trust + drops board are next slices  
**Product name:** VaryForge  
**Jeff (2026-08-20):** Diagnostics unused; Drive setup too hard / sharing his email feels wrong; phone ZIP→Files→unzip kills posting; uniqueness + posting-tracking is the no-brainer sell.

## Diagnostics (this slice)

Operators never look at failed-encode leftovers. **Hide Diagnostics** in the top nav
for every logged-in non-admin. Keep the page for site admin (and when auth is
off, for local/dev). Nav space stays for Team / later tools.

## Drive — do not make them set up Google Cloud

Operators must **not** open Google Cloud, OAuth clients, or APIs. That is
**Jeff-once** on the VaryForge GCP project (`VARIANT_DRIVE_OAUTH_*` on Railway).

**What they should do:** Settings → Drive → **copy the VaryForge email** →
share that address as Editor on their folder → paste the folder link. No
share-with-Jeff.

Connect Google as *their* account stays the later path. Until that is the
default, Studio shows `drive@varyforge.app` (or `VARIANT_DRIVE_SHARE_EMAIL`)
with a copy button. Jeff-once: create that mailbox and Connect it on Studio.

That path **already exists** per workspace. The sell-blocker is Google’s
**unverified app** screen (Drive is a restricted scope: `.../auth/drive` plus
`drive.file` + `spreadsheets`). Until the app is published/verified, only
**OAuth test users** can Connect. Adding each operator as a test user is Jeff
ops, not an operator tutorial.

### Tools email (fallback, not the default)

A branded mailbox (`drive@varyforge.app` or similar) that they share a folder
with as Editor:

- Looks less personal than Jeff’s Gmail.
- Still “share this folder with a third party” — the gray area he named.
- A `*.iam.gserviceaccount.com` robot in the UI is worse. If we use this
  fallback, show a human address (Workspace user or Google Group), never the
  SA client_email in operator copy.

**Prefer Connect Google as *their* account** so files stay in their Drive under
their identity. Tools-email share is only for people who refuse OAuth.

### Later (when Connect Google is the complaint)

1. Jeff: add operator Google emails as OAuth test users the same day as
   `new_workspace` invite. Document in `docs/ops/` (not the operator page).
2. Start Google verification / shrink scopes if a folder **picker** can replace
   full `drive` (`drive.file` + picker). Do not promise this until probed.
3. Tools-email SA/Workspace user as optional “share this folder” fallback.

Do **not** ask outside operators to create a GCP project.

## Phone — no ZIP dance

Today: Download ZIP → Files → unzip → save each mp4. That blocks
generate-on-phone → post.

**Build:** Gallery pack action **Save / Share videos** that hands the phone
**mp4 files**, not a zip.

1. If `navigator.canShare({ files })`, share the ready mp4s (Photos / Files /
   Instagram share sheet).
2. Else download each ready mp4 (no zip).
3. Keep **Download ZIP** as a secondary for desktop.

Do not unzip on the server to write into the camera roll — browsers cannot do
that. Share sheet / per-file mp4 is the lever.

Uniqueness / VMAF unchanged.

## Tracking — uniqueness + “what posted”

Reference: [Butter](https://hellobutter.io/) — Post → Track → Amplify in one
product. North star for *flow*: `docs/superpowers/specs/2026-08-20-butter-loop.md`.
Do not clone their poster, marketplace, or overlay engine.

Drop Ledger 12a (Ensure/Sync + Flagged) is the seed. The no-brainer is
**our uniqueness + a Drops board**, not Sheets and not scraping Instagram.

- One **Drops** view of packs sent to Drive: date, destination, unlabeled = pass,
  flagged / duplicate-reject as misses.
- Mark from Gallery and see it on that board.
- Identity: `job_id` + variant id + Drive file id (12b). Never caption
  filenames (Repurpose renames).
- **Paste live post URL** onto the variant (`post_url`) after the VA posts —
  click to open; views later. Not a scraper, not Eagle Browser.
- Amplify = Generate more of a **winning source**, same Fast engine — not
  Butter-style hook/overlay scrambles.
- **Official Instagram Insights** (building): Connect each professional
  tester account like Connect Google (many @handles, not one mailbox);
  **Analytics** tab is the scoreboard; Gallery keeps compact pack/tile/sheet
  views. Spec:
  `docs/superpowers/specs/2026-09-02-instagram-insights-gallery.md`.
  Ops: `docs/ops/instagram-testers.md`.

**Not:** scraping Insights, auto-post, logging into Instagram *as* the VA,
a local detector, shoutout marketplace. Connect Instagram (OAuth) is the
allowed later path — not a browser farm. The platform stays the policy
oracle (`platform_result`). Spec:
`docs/superpowers/specs/2026-08-20-post-url-tracking.md`.

## Parallel file boxes

| Track | Box | Not |
|---|---|---|
| Diagnostics | `TopNav.tsx`, `web/app/diagnostics/`, TopNav tests | Drive, Gallery zip |
| Phone save | `web/lib/` share helpers, `SourceGroup.tsx`, gallery tests | TopNav, Drive OAuth, uniqueness |
| Drive trust | this spec + `docs/ops/` Jeff-only OAuth test-user note | DestinationsPanel (onboarding PR), DropLedgerPanel |
| Drops board | `web/app/drops/` later; see butter-loop spec | engine, Stripe, Insights OAuth |

## Frozen

24-bit Fast gate, VMAF on, Fast = CPU, HQ = GPU, unlabeled = pass, invite-only.
