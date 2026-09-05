# Platform outcome tracking (learning loop) — Design

**Date:** 2026-08-18  
**PLAN phase:** 12 (after 9–11; can be sliced in parallel with 9 if HQ is delayed)  
**Status:** 12a operator UX — Studio Ensure/Sync + Flagged label shipped; 12b folder matching and 12c learning store not started  
**Product name:** VaryForge

## Why

VAs upload variants to Instagram / Reels / TikTok / Shorts. Today the **real platform is the oracle** — we do not predict “would this get flagged.” After a drop, someone has to remember which file got rejected and type that back into VaryForge. That is too slow to learn from.

We need a durable, low-friction record: **this filename, from this batch, on this platform, passed or got flagged.** Unchecked drops count as **pass**. Flagged / duplicate-reject is the signal. Over time that table is how presets, uniqueness, and (later) auto-tune get better — not a built-in Instagram detector.

This is **not** a detector. Predicting a platform’s verdict stays out of scope (see `CLAUDE.md`). Auto-scraping IG/TikTok accounts is a later, optional automation — not required for the learning store.

## What already exists (do not rebuild)

| Piece | Where | Gap |
|---|---|---|
| `platform_result` on each variant (`passed` / `duplicate_reject` / `flagged` / `unknown` / `null`) | Manifest, Gallery variant sheet, `POST /api/variants/{source_id}/{index}/platform-result` | Manual, per-clip; unlabeled = pass so VAs skip Passed |
| Drop Ledger Google Sheet | `variant_maker/server/drop_ledger.py`, `/api/drop-ledger/*`, Studio **Settings → Drive → Drop Ledger** | 12a UI shipped: status + **Ensure sheet** + **Sync from Studio** + **Open sheet**. VAs still don’t live in Sheets |
| Drive export | Gallery → Send to Drive | Folder is the drop tray; **no automatic match** from “this file in the folder got flagged” back to the variant row |
| Uniqueness / seed / strength on the ledger row | Sheet columns | Unused for bias until Phase 12 reads outcomes |

**Default for learning:** `platform_result is null` (nobody labeled) **≡ pass.** Only explicit `duplicate_reject` or `flagged` is a miss. Do not require VAs to click Passed on every clip.

## Goal

1. **Near-term (12a — operator UX):** After a Drive drop, it is obvious in **one place** (Studio + the Drop Ledger sheet) which files went out and which were flagged. Labeling a miss is one action (Gallery, or a row in the sheet that syncs back). Unlabeled rows stay pass.
2. **Mid (12b — folder ↔ ledger):** Filename / Drive file id on the ledger (`drop_url`) so “the one that got taken down in the Reels folder” maps to `job_id` + `variant_id` without hunting.
3. **Later (12c — learning store):** Same rows (Sheet is fine until it is not; a DB is optional when we want queries / API, not on day one). Feed **flagged** recipes into uniqueness / preset / Phase 11. Still no on-box “will IG catch this” model unless we spin that as a **separate** project.

## Success looks like

- VA generates → Send to Drive → posts from that folder.
- If IG is quiet, they do nothing; ledger stays unlabeled = pass.
- If a clip is flagged or duplicate-rejected, they mark **that file** (Studio or sheet). Gallery and sheet agree.
- We can list “flagged this week” with seed, preset, uniqueness, strength — enough to change the next batch.

## Non-goals

- Logging into Instagram/TikTok as the VA and scraping insights.
- A local classifier that claims to predict platform policy.
- Replacing the manifest `platform_result` slot — extend it, don’t fork a second truth.
- **View counts / “is it getting push?”** — that is the Instagram Insights
  Gallery track (`2026-09-02-instagram-insights-gallery.md`). Official
  Connect, pack rollup, amplify winners. Insights must never write
  `flagged` / `duplicate_reject`. Phase 12 stays policy labels only.

## Suggested slices (when we build)

1. ~~Studio: Drop Ledger status + **Ensure sheet / Sync from Studio** (Drive OAuth is already live).~~ **12a shipped** — Settings → Drive panel. `VARIANT_DROP_SHEET_ID` still documented in Railway + Drive OAuth ops.
2. ~~Variant sheet: keep Passed / Duplicate rejected; add **Flagged**; treat empty as pass.~~ **12a shipped**
3. On Send to Drive success, write `drop_url` / Drive file id onto the ledger row. **(12b)**
4. Optional: “mark from folder” — pick a Drive file name, set `flagged`. **(12b)**
5. Export or query: flagged rows → JSON/CSV for later tuner work. Promote to a small DB only if Sheets becomes the bottleneck. **(12c)**

## Filename / Repurpose.io

There is **no Repurpose.io API**. After Send to Drive, VAs (or Repurpose) **rename
the file to the caption text**. Matching on VaryForge’s original filename will fail.

Do **not** key learning on the Drive display name after captioning.

Stable identity (use these, in order):

1. **Drive file id** captured at upload (`drop_url` / file id on the ledger row).
   Survives rename if they keep the same file.
2. **VaryForge variant id** (`job_id` + `source_id` + index) in the sheet and,
   if we need a human handle in the folder, a **short id in the filename prefix**
   (e.g. `v01_8a3f1c2d__`) that they can leave on or we strip into caption metadata
   before Repurpose — never rely on the caption becoming the only name.
3. Content hash of the bytes we uploaded (if the file is replaced, hash changes).

Auto-checking Instagram remains optional later (no official “was this flagged”
API we own). Until then: unlabeled = pass; someone marks **flagged** on the
ledger row (by Drive file id, not by caption title).

## Invariants

- Color / quality / uniqueness pipelines stay the source of **what we rendered**. Outcomes are labels on those rows.
- Sheet labels must not be blanked on sync (already true in `drop_ledger.py`).
- One company Drive + one ledger for the Studio instance (same as destinations today).
