# VaryForge Google Drive Export — Design

**Date:** 2026-07-21  
**Status:** Brainstorm approved — awaiting user spec review  
**Product name:** VaryForge (codebase: `variant-maker`)  
**Approach:** Approach 1 — Gallery **Send to Drive** on the existing farm Drive client (service account), with destination records shaped for future OAuth.

---

## 0. Decisions locked in brainstorm

| Topic | Decision |
|-------|----------|
| Approach | Gallery manual “Send to Drive” (Approach 1) |
| Auth (v1) | Company shared Drive via Google **service account** already used by farm |
| Destinations | Saved list: friendly name + folder ID parsed from a pasted Drive folder link |
| Trigger | Manual only — user picks destination after selecting variants |
| What uploads | Video files only; variants with `status: "ok"` |
| Progress | Export job with progress + success/fail; partial retry of failed items |
| Collision | Keep source filenames; suffix on name collision in the target folder |
| Forward-compat | Destination records include `auth_mode: "service_account"` |
| Out of v1 | Per-user OAuth/SaaS, auto-upload, ZIP/manifest packaging, view-only public links, full Drive tree browse |

---

## 1. Goal

Let Studio users push finished gallery variants into a company shared Google Drive folder in one explicit action, without leaving VaryForge.

**Success looks like**

1. Operator saves one or more Drive destinations (name + folder from a pasted link).
2. In Gallery, they select `ok` variants and choose **Send to Drive**.
3. They pick a destination; the server uploads those video files into that folder.
4. UI shows per-file progress and a clear success / partial-fail / fail outcome, with retry for failures only.

**Non-goals for this release**

- Per-user Google OAuth or multi-tenant SaaS Drive auth
- Auto-upload after a render job finishes
- ZIP bundles, manifests, or side-car metadata uploads
- Creating or sharing view-only public Drive links
- Browsing the full Drive folder tree in the UI
- Replacing or reviving the parked Drive **farm inbox runner** (`variant-farm run`)

---

## 2. Relationship to existing farm Drive

VaryForge already has a Google-aware module at `variant_maker/farm/drive.py`:

- `DriveClient` — list / download / create-folder / find-folder / upload
- `GoogleDrive` — real adapter (service account JSON or OAuth token)
- `FakeDrive` — in-memory client used by farm tests

**This feature reuses that client.** Studio export is a new control-plane path that calls the same upload surface. It is **not** the farm automation design (`docs/superpowers/specs/2026-06-27-drive-farm-automation-design.md`): no inbox poll, no ledger keyed on source sha256, no per-client recipe sweep.

| Concern | Farm inbox runner | Studio Drive export (this spec) |
|---------|-------------------|----------------------------------|
| Trigger | Cron / `variant-farm run` sweep | Manual Gallery action |
| Direction | Drive → render → Drive | Local Pod workspace → Drive |
| Identity | Client configs + ledger | Saved destinations + export jobs |
| Code seam | `farm/runner.py` | New Studio API + export job runner |

If farm Drive extras (`google-api-python-client`, `google-auth`) or the service-account JSON path are missing on the Pod, Send to Drive is disabled with an honest message — see §6.

---

## 3. Auth (v1)

**Mechanism:** one Google service account JSON key mounted on the Pod (same pattern as farm auth: path to a JSON file).

**Folder access:** each destination folder must be shared with the service account email as **Editor** (or equivalent write access). Ownership of the folder can be any account in the company shared Drive; identity is the folder ID, not “My Drive of the SA.”

**Probe on add:** when creating or updating a destination, the server:

1. Parses the pasted folder URL → folder ID.
2. Uses the farm Drive client to confirm the folder exists (metadata / list children succeeds for that id and mime is a folder).
3. Confirms write access with a real upload probe: upload a tiny temporary marker file into the folder, then trash/delete it. Listing alone is not enough — Editor share mistakes must fail before the destination is saved. (`DriveClient` may need a small trash/delete method for cleanup; that is in scope for this feature, not a farm-runner change.)
4. Rejects the save with a clear error if the folder is missing, not a folder, or not writable (“Cannot write to this folder — share it as Editor with `<sa-email>`”).

**Runtime misconfig:** if the SA JSON path is unset, unreadable, or credentials fail to build, Drive export APIs return a structured “not configured” / “auth failed” state. The Gallery action and Destinations UI stay visible but disabled (or show the same honest banner) — never pretend upload will work.

**Not in v1:** interactive OAuth consent, storing user refresh tokens, or per-operator Google identities. Destination records still carry `auth_mode: "service_account"` so a later OAuth mode can coexist without a schema break.

---

## 4. Destinations

### Record shape (forward-compatible)

```json
{
  "id": "dst_…",
  "name": "Reels drops",
  "folder_id": "1AbC…",
  "auth_mode": "service_account"
}
```

| Field | Meaning |
|-------|---------|
| `id` | Server-assigned stable id |
| `name` | Friendly label shown in pickers |
| `folder_id` | Google Drive folder ID (never store the full URL as the source of truth) |
| `auth_mode` | Always `"service_account"` in v1; reserved for future `"oauth"` |

### URL → folder ID

Accept common Drive folder link forms and extract the folder ID, including at least:

- `https://drive.google.com/drive/folders/<ID>`
- `https://drive.google.com/drive/u/0/folders/<ID>`
- Links with query strings (`?usp=sharing`, etc.)

Reject non-folder file links and bare garbage with a validation error before probe. Pure URL-parse helpers are unit-tested without Google.

### Persistence

Destinations are stored on the Pod (server-side), not in browser localStorage — so every operator on that Studio instance shares the same destination list. Exact storage file/format is an implementation detail (JSON under the control-plane workspace is fine); the public contract is the CRUD API below.

### CRUD + test access

| Action | Behavior |
|--------|----------|
| List | All saved destinations |
| Create | Name + pasted link → parse → probe → persist |
| Update | Rename and/or new link (re-probe if folder changes) |
| Delete | Remove destination; does not delete Drive contents |
| Test access | Re-run the write probe against the saved `folder_id` without changing the record |

---

## 5. Export flow

```
Gallery: select ok variants
  → Send to Drive
  → pick destination
  → POST /api/drive/exports
  → export job uploads each video via farm DriveClient.upload
  → persist per-file + job status
  → UI shows progress / success / fail
  → on partial fail: retry failed items only
```

### Eligibility

- **In:** variants with `status === "ok"` that the user selected (or that remain after filtering a mixed selection).
- **Out:** `best_effort`, `corrupt`, in-flight, and non-video artifacts. Manifest JSON and thumbnails are not uploaded in v1.
- If the selection contains zero `ok` videos after filter, do not start an export; tell the user why.

### Request (conceptual)

`POST /api/drive/exports` body identifies:

- `destination_id`
- List of variant refs (`source_id` + `index`, or equivalent stable file identity already used by Gallery)

Server resolves each ref to a local video path under the workspace, verifies `ok`, then enqueues an export job.

### Upload behavior

- **Filename:** use the variant’s existing filename (e.g. `v01.mp4`).
- **Collision:** if the destination folder already has a file with that name, upload with a deterministic suffix (e.g. `v01 (1).mp4`, then `v01 (2).mp4`, …) rather than overwrite. Do not rename successful non-colliding files.
- **Order:** sequential or bounded parallel uploads are an implementation choice; progress must still be per-file.
- **No ZIP, no subfolder-per-batch** in v1 — files land directly in the destination folder.

### Export job status

Persist enough to survive a page refresh:

- Job: `pending` → `running` → `succeeded` | `partial` | `failed`
- Per file: `pending` | `uploading` | `succeeded` | `failed` (+ error message when failed)
- On success: store Drive file id when the client returns it

**Partial retry:** `POST` (or equivalent) retry on an existing export job re-uploads only files still in `failed` (or explicitly selected failures), leaving successes untouched.

### Progress UX

Mirror existing Studio job patterns where practical (poll and/or SSE). Minimum bar:

- While running: counts (done / total) and current filename
- On complete: success toast/summary, or partial-fail list with retry
- Clear errors for auth, missing file, Drive API quota/permission failures

---

## 6. UI

### Destinations settings

A settings surface (Studio settings or dedicated Drive destinations page — same information architecture family as other Pod config) for:

- List destinations (name, folder id truncated, auth mode)
- Add / edit / delete
- **Test access** button
- Banner when Drive is not configured on the Pod

### Gallery action

- Multi-select (or current selection model) of variants → **Send to Drive**
- Destination picker (saved destinations only — no tree browse)
- Disabled / honest empty state when:
  - Drive SA not configured
  - No destinations saved
  - Selection has no `ok` videos

Do not show a fake success path. Prefer disabled control + short reason over a dead-end modal.

---

## 7. API surface (contract-level)

Exact path names may match existing `/api/…` conventions; behavior is fixed:

| Endpoint intent | Notes |
|-----------------|-------|
| Drive config status | Whether SA is configured / reachable enough to attempt exports |
| Destinations CRUD | Create/list/update/delete |
| Destination test | Probe write access for one destination |
| Create export | Start job for `ok` variant refs → destination |
| Get export | Job + per-file status |
| Retry export failures | Re-queue failed files only |

All mutating Drive calls go through `DriveClient` (real `GoogleDrive` on Pod; fakes in tests).

---

## 8. Error handling (explicit)

| Situation | User-visible outcome |
|-----------|----------------------|
| SA JSON missing / invalid | Drive disabled; config banner |
| Folder link unparseable | Validation error on save |
| Folder not found / not writable | Probe fails; destination not saved (or test fails) |
| Variant not `ok` or file missing | Skip or reject that item; do not mark job fully succeeded |
| Mid-upload Drive API error | That file `failed`; others continue; job → `partial` or `failed` |
| Collision | Suffix and upload; not an error |

---

## 9. Testing

**Required (no live Google)**

- URL parse: folder links → folder ID; reject file links / junk
- Destination CRUD + validation + probe wiring against `FakeDrive` / test doubles
- Export eligibility: only `ok` videos included; mixed selection filtered
- Export runner: upload calls, collision suffix, partial failure + retry, status persistence
- UI/API: Drive-not-configured disabled path

**Optional**

- Pod smoke against a real shared test folder with the company SA (manual or marked integration); not required for merge.

---

## 10. Out of scope / later

These stay deferred; v1 schemas avoid painting into a corner:

| Later | Notes |
|-------|--------|
| Auto-upload after render | Hook on job completion; still uses destinations |
| Per-user OAuth | New `auth_mode`; destinations may gain user binding |
| ZIP / manifest upload | Packaging step before or instead of loose files |
| View-only public links | Separate sharing API; not implied by upload |
| Full Drive tree browse | Picker UI over `list_files`; destinations remain ID-based |

---

## 11. Scope check

This design is one implementation plan:

1. Wire Pod SA config + Drive status into Studio.
2. Destinations CRUD + URL parse + probe.
3. Export job + Gallery Send to Drive + progress/retry.
4. Tests with fake Drive client.

No farm-runner revival, no OAuth product work, and no packaging features in the same plan.
