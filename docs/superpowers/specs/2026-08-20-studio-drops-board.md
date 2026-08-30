# Studio drops board (posting tracker) — spec

**Date:** 2026-08-20  
**Status:** Spec — implement after Drop Ledger 12a lands; do not start engine work  
**Product name:** VaryForge  
**Depends on:** Phase 12a in PR `cursor/drop-ledger-studio-c975` (Ensure / Sync + Flagged). Assume it merges. Do **not** re-implement it here.  
**Related:** `2026-08-18-platform-outcome-learning.md` (labels + 12b `drop_url`), `2026-08-20-operator-friction.md` (Tracking), `2026-08-20-butter-loop.md` (flow north star, not this backlog)

Jeff’s sell: **uniqueness variants + posting tracking** in one Studio. A spoofer
only ships files. Agencies need “what we posted / what got flagged” next to
Generate.

This is **not** a detector. The real platform is the oracle. Unlabeled
`platform_result` = **pass**. `flagged` / `duplicate_reject` = **miss**.

Fast uniqueness stays **24 bits vs source / 24 vs peers**. Do not propose
raising it (not 32, not 55%).

---

## 1. Why

VAs generate in Studio, Send to Drive, post from that folder (phone or
Repurpose). Today the trail lives in a Sheet and in Gallery labels that you
only see if you open each clip. Agencies cannot answer, in one glance:

- What went out this week, to which destination?
- What is still unlabeled (treat as pass)?
- What got flagged or duplicate-rejected?

That board, sitting **in Studio next to Generate**, is the product vs “just a
spoofer.” Uniqueness is why the files are worth posting. The board is why they
stay in VaryForge instead of a spreadsheet.

Flow we already own (do not rebuild): Generate Fast → Gallery → Send to Drive /
pack split → Drop Ledger labels. The missing room is a **list of Drive-sent
packs**, not a new engine.

---

## 2. What 12a already gives (do not redo)

Assume PR `cursor/drop-ledger-studio-c975` is on the branch you implement on.

| Surface | Behavior |
|---|---|
| Drive page **Drop Ledger** panel | Status, **Ensure** sheet, **Sync** rows, open spreadsheet URL |
| Gallery variant sheet | **Passed** / **Duplicate rejected** / **Flagged** → `POST /api/sources/{id}/variants/{index}/platform-result` |
| Gallery cards | Passed / duplicate / flagged badges |
| Sheet write-through | Gallery label updates the ledger `platform_result` cell |
| Default | `platform_result` null / empty ≡ **pass**. Nobody must click Passed. |

Ledger upsert key is already `job_id` + `variant_id` (`{source_id}:{index}`).
The sheet has a `drop_url` column; 12a leaves it **empty**. Filling it is 12b
(slice 2 below), not 12a.

If 12a is missing on your branch, stop and rebase onto it. Do not invent a
second label store.

---

## 3. Drops board (v1)

**Where:** Studio product chrome, next to Generate. v1 is **our** board — a
Gallery **Sent to Drive** list (and/or a small `/drops` page using the same
data). Do not add Instagram login. Do not wait on a competitor screenshot to
ship this list.

**Who appears:** variants that actually **sent to Drive** (export file
`status=succeeded`). Generated-but-not-sent clips stay in Gallery “All”; they
are not drops.

**Row (variant or pack group — pack group preferred):**

| Column | Source |
|---|---|
| Date | Export job `created_utc` (send day), not caption time |
| Destination | Saved Drive destination **name** (`destination_id` → Destinations store). Pack split shows main / trial / growth as separate sends. |
| Count | Files succeeded on that export |
| Outcome | Unlabeled or `passed` → **pass**. `flagged` or `duplicate_reject` → **miss** with that label. `unknown` is not a miss. |

Click a row → existing Gallery variant sheet (same mark actions as 12a). Marks
on the board and in Gallery are the same `platform_result`. Drop Ledger remains
the durable sheet; the board does not replace it.

**Filter: “flagged this week.”** Drive-sent variants whose result is `flagged`
or `duplicate_reject`, and whose **send** `created_utc` is in the last 7 days.
v1 does **not** add a label-timestamp column. Week = when we sent, not when
someone clicked Flagged.

Also useful (same data, not extra product): All sent / This week / Misses only.

**Not in v1 UI:** calendars, daily posting goals, account-proxy queues, views /
CPM charts, Butter-style poster, scheduler clones.

---

## 4. Identity (never the caption title)

Stable key, in order:

1. **`job_id`** — generate job that produced the file  
2. **`variant_id`** — `{source_id}:{index}` (same as Drop Ledger)  
3. **`drive_file_id`** — Google file id from a **successful** Send to Drive
   (Phase **12b**). Persist on the export file (already stored as
   `ExportFile.drive_file_id`) **and** on the ledger `drop_url` cell.

Do **not** key the board, ledger, or “find this flagged file” on:

- Caption text  
- Caption-derived Drive **filename** (Send-to-Drive can already name the upload
  from a caption; Repurpose **renames** again)  
- Display name in the folder after the VA or Repurpose edits it  

There is no Repurpose API. After rename, only Drive file id still points at the
same blob. If they replace the file, id/hash change — that is a new drop, not
the old row.

Optional later (not v1): short id prefix on the uploaded filename
(`v01_8a3f1c2d__…`) so a human can still grep the folder. Never treat the
caption as the id.

---

## 5. Explicit non-goals

| Out | Why |
|---|---|
| Instagram / TikTok / YouTube **scrape** or official insights login | No account farm. Platform stays the oracle via manual miss labels. |
| **Auto-post** / native scheduler / Butter poster | Repurpose or the phone posts. Studio sends to Drive. |
| Local **predictor** (“would IG catch this”) | Separate project. `CLAUDE.md`. Manifest `platform_result` only. |
| **Stripe**, public signup, Postgres | Billing wave; not this board. |
| Uniqueness **55%** / raising the **24-bit** Fast gate | Escalates whole Fast 20-packs. Frozen. |
| **Pixel-AI** / overlay / hook-scramble clone | Cheap look. Our variants stay real (color + VMAF + uniqueness). |
| Re-implementing **12a** Drop Ledger panel / Flagged buttons | Lands on the other PR. |
| Touching **sampler**, uniqueness math, RunPod workers, VMAF | Wrong box. |

---

## 6. Implementation slices

Ship in this order. Each slice is its own PR. Stay in the **file box**.

### Slice 1 — Gallery / Drive-sent filter (the board)

Join data we already have. No new truth store.

**Data:**

- `ExportStore` JSON under `{workspace}/drive/exports/` — per job:
  `created_utc`, `destination_id`, `folder_id`, files with `source_id`,
  `index`, `status`, `drive_file_id` (filled on upload success today).
- There is **no** `GET /api/drive/exports` list yet; only get-by-id. Add
  `ExportStore.list()` + `GET /api/drive/exports` (succeeded files, newest
  first). Join `destination_id` → destination **name**. Join
  `source_id`+`index` → JobStore / Gallery `platform_result` + `job_id`.
- Filter Gallery (or `/drops`) to those succeeded export files.
- Chip **Flagged this week** as specified in §3.

**Box:**

| Touch | Do not touch |
|---|---|
| `variant_maker/server/drive_exports.py` (`list()` only) | `sampler.py`, `filtergraph.py`, `pipeline.py` |
| `app.py` Drive export **list** route only | `runpod_runner.py`, `runner.py`, uniqueness, quality |
| `web/app/gallery/` toolbar + filter helpers (`web/lib/gallery.ts`) | Drop Ledger Ensure/Sync panel (12a) |
| Optional `web/app/drops/` if a dedicated page is cleaner than a chip | `web/app/page.tsx` Generate form, TopNav unless adding one **Drops** link |
| `web/lib/api.ts` + `types.ts` export-list types | Destinations CRUD, OAuth, captions |
| Tests: export list + gallery filter | Engine / Fast worker tests |

Empty state: “Nothing sent to Drive yet — Generate, then Send to Drive.” Honest
if Drive is disconnected.

### Slice 2 — 12b `drop_url` (Drive file id on send)

**Trigger in product terms:** a flagged file cannot be found because Repurpose
renamed it to the caption.

**Build:** on Send to Drive **file success**, write `drop_url` on the ledger row
keyed by `job_id` + `variant_id`. Value = Drive **file id** (or a
`drive.google.com/file/d/{id}` URL that still contains that id). Use the id
already returned into `ExportFile.drive_file_id`. Same write on pack-split
exports (one export job per destination).

Preserve-if-set already includes `drop_url` — do not blank it on Sync. Add
`update_drop_url_cell` next to `update_platform_result_cell` (or upsert a
one-field row). If the ledger row does not exist yet, insert or no-op with a
log; do not fail the upload.

**Box:**

| Touch | Do not touch |
|---|---|
| `drop_ledger.py` (drop_url write) | sampler, uniqueness, RunPod |
| Export runner **after** successful upload (`drive_exports.py`) | Gallery filter UI (slice 1) |
| `app.py` only if the runner cannot see sheets/workspace | OAuth, tenants, Team |
| `tests/server/test_drop_ledger_api.py` + export tests | `web/` except a later “open in Drive” link keyed by id |

Board / Gallery still must not search by caption filename after this lands.

### Slice 3 — optional win-rate strip

Tiny readout on Gallery (or Studio home under Generate), Drive-sent only:

- `sent` = succeeded export files in the window (week / all)  
- `misses` = those with `flagged` or `duplicate_reject`  
- **Win rate** = `(sent - misses) / sent`  
- Copy: unlabeled counts as pass. Do not nag to click Passed.

Skip this slice if slice 1 already shows counts. No charts, no Stripe, no
predictor.

**Box:** Gallery toolbar or a short strip component + the list payload from
slice 1. Not Generate advanced panel, not workers.

---

## 7. Competitor

Jeff to attach URL / screenshot.

Do **not** copy their information architecture until we have it. **v1 is our
board** (§3–§6): Drive-sent list, date, destination, pass/miss, flagged-this-week.

Butter ([hellobutter.io](https://hellobutter.io/)) is already the *loop* north
star in `2026-08-20-butter-loop.md` (Post → Track → Amplify). That does **not**
authorize cloning their poster, calendar, marketplace, or analytics IA. If Jeff
pastes a **different** tracker (or a Butter app screenshot), park it here and
revisit layout only — do not change uniqueness, 12a labels, or identity.

**URL:**  
_paste here_

**Screenshot / notes:**  
_paste here_

Until something is pasted, implement v1 as specified. No extra research tab,
no scraping the competitor.

---

## Frozen

- Unlabeled after a drop = pass; flagged / duplicate_reject = miss  
- Fast uniqueness **24 / 24** bits; do not raise  
- Color correctness, zero-mean color, VMAF floor, audio sync  
- Fast = CPU, HQ = GPU; do not split one pack across both  
- Invite-only; no detector; no IG login  
- Manifest `platform_result` remains the label; do not fork a second enum  
