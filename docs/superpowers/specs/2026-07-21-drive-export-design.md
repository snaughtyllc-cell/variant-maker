# VaryForge Google Drive Export — Design

**Date:** 2026-07-21  
**Status:** Implemented (SA + OAuth option C)  
**Product name:** VaryForge (codebase: `variant-maker`)  
**Approach:** Approach 1 — Gallery **Send to Drive** on the farm `DriveClient`, with destinations. Auth: service account **or** company OAuth (option C).

---

## 0. Decisions locked in brainstorm

| Topic | Decision |
|-------|----------|
| Approach | Gallery manual “Send to Drive” (Approach 1) |
| Auth (v1) | Company shared Drive via Google **service account** (when keys available) |
| Auth (option C) | **OAuth Web client** + refresh token on Pod — required when SA JSON keys are blocked |
| Destinations | Saved list: friendly name + folder ID parsed from a pasted Drive folder link |
| Trigger | Manual only — user picks destination after selecting variants |
| What uploads | Video files only; variants with `status: "ok"` |
| Progress | Export job with progress + success/fail; partial retry of failed items |
| Collision | Keep source filenames; suffix on name collision in the target folder |
| Forward-compat | Destination `auth_mode`: `"service_account"` or `"oauth"` |
| Out of scope | Multi-tenant per-user SaaS OAuth, auto-upload, ZIP/manifest, public links, full tree browse |

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

## 3. Auth

Two mechanisms; **OAuth is the path that must work** when Google Cloud blocks downloadable SA keys. Prefer a stored OAuth refresh token over SA when both are present.

### 3a. Service account (optional)

**Mechanism:** one Google service account JSON key mounted on the Pod (`VARIANT_DRIVE_SERVICE_ACCOUNT_JSON`).

**Folder access:** share each destination folder with the SA email as **Editor**.

### 3b. OAuth (option C — company, admin-once)

**Mechanism:** Google Cloud **OAuth 2.0 Client ID** (Web application) — not an SA JSON key. Env on Pod:

| Env | Purpose |
|-----|---------|
| `VARIANT_DRIVE_OAUTH_CLIENT_ID` | Web client ID |
| `VARIANT_DRIVE_OAUTH_CLIENT_SECRET` | Web client secret |
| `VARIANT_DRIVE_OAUTH_REDIRECT_URI` | Optional override; default derived from request / documented RunPod URL |

**Redirect URI (RunPod proxy, same origin as UI):**  
`https://li25cvxk21j8jn-8888.proxy.runpod.net/api/drive/oauth/callback`  
(Next.js rewrites `/api/*` → FastAPI so cookies/redirect stay on the proxy host.)

**Flow:** Settings → **Connect Google** → Google consent (Drive scope sufficient to upload into folders the signed-in user can access) → callback stores refresh token at `{workspace}/drive/oauth_token.json` → status shows connected email → destinations / Send to Drive use `GoogleDrive(oauth_token=…)`. **Disconnect** deletes the token file.

**Folder access (OAuth):** the signed-in Google account must already be able to write the destination folder (owner or Editor). No SA share step.

### 3c. Probe on add (both modes)

When creating or updating a destination, the server:

1. Parses the pasted folder URL → folder ID.
2. Confirms the id is a folder via `DriveClient.get_file`.
3. Write probe: upload a tiny marker, then trash it.
4. Rejects with a clear error if missing / not a folder / not writable (SA message includes share-with-email when known; OAuth message names the connected account).

**Runtime misconfig:** no usable SA and no OAuth token → Drive disabled with an honest banner. If OAuth client env is set but not connected, UI offers **Connect Google**.

---

## 4. Destinations

### Record shape (forward-compatible)

```json
{
  "id": "dst_…",
  "name": "Reels drops",
  "folder_id": "1AbC…",
  "auth_mode": "oauth"
}
```

| Field | Meaning |
|-------|---------|
| `id` | Server-assigned stable id |
| `name` | Friendly label shown in pickers |
| `folder_id` | Google Drive folder ID (never store the full URL as the source of truth) |
| `auth_mode` | `"service_account"` or `"oauth"` — matches the Drive client in use when the destination was saved |

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
- **Connect Google** / connected email + **Disconnect** when OAuth client is configured

### Gallery action

- Multi-select (or current selection model) of variants → **Send to Drive**
- Destination picker (saved destinations only — no tree browse)
- Disabled / honest empty state when:
  - Drive not connected (no OAuth token and no SA)
  - No destinations saved
  - Selection has no `ok` videos

Do not show a fake success path. Prefer disabled control + short reason over a dead-end modal.

---

## 7. API surface (contract-level)

Exact path names may match existing `/api/…` conventions; behavior is fixed:

| Endpoint intent | Notes |
|-----------------|-------|
| Drive config status | Whether SA or OAuth is ready; `auth_mode`, connected email, `oauth_available` |
| OAuth start | Redirect to Google consent |
| OAuth callback | Exchange code → persist refresh token → redirect to Settings |
| OAuth disconnect | Clear stored token |
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
| SA JSON missing / invalid and no OAuth token | Drive disabled; config banner + Connect Google when OAuth client env set |
| OAuth not connected | Connect Google button; destinations/export disabled until ready |
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
| Multi-tenant per-operator OAuth | Company admin-once OAuth is in; per-user binding deferred |
| ZIP / manifest upload | Packaging step before or instead of loose files |
| View-only public links | Separate sharing API; not implied by upload |
| Full Drive tree browse | Picker UI over `list_files`; destinations remain ID-based |

---

## 11. Scope check

Implementation plan:

1. Wire Pod SA config + Drive status into Studio.
2. Destinations CRUD + URL parse + probe.
3. Export job + Gallery Send to Drive + progress/retry.
4. **OAuth option C:** client env, token store, start/callback/disconnect, UI Connect/Disconnect.
5. Tests with fake Drive client + faked OAuth exchange (no live Google in CI).

No farm-runner revival and no packaging features in the same plan.
