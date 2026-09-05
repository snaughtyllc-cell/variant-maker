# Per-job isolation (files, object prefixes, Drive, publication)

**Date:** 2026-09-05  
**Status:** Encode — layout + publication rules in-process. Live keys are still the legacy `inputs/{source_id}/` shape until a cutover copies objects into the new namespace.  
**Product name:** VaryForge  
**Not this slice:** reconstruct-first, HQ GPU occupancy, uniqueness/VMAF changes, SQLite cutover, always-on workers.

Astra’s contract: **keep** the tenant/job hierarchy, per-workspace Drive credentials, and attempt fencing. **Change** object keys to include tenant/job/attempt, make scratch attempt-specific, and put Drive **publication** under control-plane authority.

The durable authority is the job record — not occupancy:

`(tenant_id, job_id, current_attempt_id, fencing_token, status)`

`workspace_id` is the canonical tenant id. Persist the record and publication ops on local disk. `job.json` stays a readable snapshot. SQLite transactions are a later fit for one process; in-memory occupancy is reconstructed after restart. Redis is not required.

Module: `variant_maker/server/job_isolation.py` (pure).

## Frozen

- Color correctness, VMAF floor, uniqueness **24 vs source / 24 vs peers**.
- Do not split one 20-pack across machines.
- Min workers 0. Overnight Fast compute may be $0; object storage can still cost money.
- Attempts own immutable staged artifacts. The control plane owns the decision to publish and the authority to delete.

## 1. Worker scratch

```text
{TMP_ROOT}/tenants/{tenant_id}/jobs/{job_id}/attempts/{attempt_id}/{random}/
  in/
  out/
  work/
```

Keep `mkdtemp`, but create it **beneath** the attempt directory. IDs come from the authorized assignment; `safe_id` rejects traversal and `..`.

- Supervisor creates the directory with restricted permissions and passes the absolute path into every subprocess.
- Success: delete after outputs are durably uploaded and acknowledged.
- Cancel: stop that attempt’s process group, wait, close transfers, then delete.
- Crash: ephemeral disk dies with the worker. On a surviving worker, a janitor deletes abandoned dirs only when `may_delete_abandoned_scratch(process_owns=False)`.

No global `/out`, shared progress files, or reusable filenames outside the attempt root. Fence expiry triggers supervisor cancellation. A fencing token cannot stop filesystem writes: **never reuse** that directory; terminate the worker if its processes cannot be stopped.

## 2. Object storage

```text
tenants/{tenant_id}/jobs/{job_id}/
  inputs/{source_id}/{artifact_id}
  attempts/{attempt_id}/outputs/{source_id}/{artifact_id}
  attempts/{attempt_id}/manifest.draft.json
  manifests/{publication_id}.json
```

The 12-hex `source_id` remains a label. It is **not** authorization.

| Rule | Detail |
|---|---|
| Inputs | Immutable after acceptance. |
| Retries | New `attempt_id` prefix. Same job id. |
| Worker IAM | Exact-object reads of this job’s inputs; uploads only under **this attempt**. No bucket listing, no delete, no canonical-manifest writes. |
| Create-only | Duplicate write is ok only if checksums match (`create_only_ok`). |
| Cleanup | Control plane only; delete objects recorded as owned by that job and eligible under retention. |
| Late uploads | A stale attempt’s credentials may still work; they must land only in that obsolete attempt prefix and **never** become published. |

`authorize_object_key` is prefix membership under `(tenant_id, job_id)`, never `source_id` alone.

**Legacy:** `inputs/{source_id}/` and `outputs/{source_id}/` (`media_links.input_key`). Resolve exact keys through an authorized job record. Copy into the namespaced prefix **before** a new attempt reads them. Do not infer ownership from `source_id`.

## 3. Drive destination

Persist when the destination is selected:

`tenant_id, job_id, workspace_id, drive_credential_ref, drive_account_id, destination_folder_id, destination_revision`

Verify the operator’s workspace access and folder authorization. Freeze the binding for execution; changing it is an authorized update and invalidates pending publication. The worker cannot supply a replacement folder or credential.

**Workers do not receive a Drive access token** (`worker_may_hold_drive_token` is false for publish and input-read). Short-lived tokens still authorize whatever the OAuth grant can see; they are not bound to our fence. [Google OAuth](https://developers.google.com/identity/protocols/oauth2/web-server)

The control plane publishes from staged object-storage artifacts: resolve credential + folder from the durable binding, check the current attempt, journal each Drive op, then send it.

Create-new uploads; persist returned Drive file IDs. Collision **rename** is fine (`unique_upload_name`); never find a name and overwrite it. Retry reconciliation uses recorded IDs, not filenames.

Live still mints a short-lived token for RunPod **input** download. Cut that path by staging Drive sources onto object storage in the control plane before dispatch — not in this encode’s call sites.

## 4. Manifest and publication

Control-plane job root (workspace_id = tenant):

```text
{JOB_ROOT}/job.json
{JOB_ROOT}/{source_id}/in/
{JOB_ROOT}/attempts/{attempt_id}/{source_id}/out/
{JOB_ROOT}/attempts/{attempt_id}/manifest.draft.json
{JOB_ROOT}/manifests/{publication_id}.json
```

Draft: artifact keys, checksums, ownership, attempt, destination revision. Final manifest is immutable; the job record holds the publication pointer.

`finalize_allowed` / `cancel_outcome`:

- Finalization needs the current attempt/fence, no cancellation, artifacts confirmed.
- Cancel after `completed`/`done` → **already_completed**.
- Cancel before completion prevents the final commit and schedules cleanup of uncommitted exports.
- Stale attempt cannot update progress, current-attempt state, final manifests, or publication pointers.

Drive HTTP and local disk are **not** one atomic transaction. An in-flight upload can finish after cancel: record it, clean up only that job’s uncommitted files, never report published. Reconcile unfinished publication on restart before retry.

## 5. Cleanup (`retain_until`)

| Data | Completed | Cancelled / failed |
|---|---|---|
| Worker scratch | Delete after upload ack | Delete after process exit; janitor on boot |
| Local media cache | Delete after publication verification | 24 hours |
| Object inputs | 7 days | 7 days |
| Selected output objects | 7 days after publication | 24 hours unless checkpointed for retry |
| Superseded attempt outputs | 24 hours | 24 hours |
| Job records, manifests, sanitized logs | 30 days | 30 days |
| Published Drive files | Keep until explicit authorized deletion | Delete only app-created, uncommitted exports tracked by ID |

Skip active jobs, publication in flight, and checkpointed artifacts. Deletion intent is durable and idempotent. Never recursively delete the operator’s destination folder. Cleanup runs on the control plane; CPU workers need not exist overnight.

Today’s Gallery keep (7 days of `job.json`) and `VARIANT_OUTPUT_KEEP_HOURS` (48h download objects) stay until this table is wired as `retain_until` on each object.

## 6. Forbidden

- Listing or reading another tenant’s prefix (guessed ids, leaked URLs).
- Using a Drive folder merely because the OAuth account can access it.
- Accepting a worker callback on `job_id` alone.
- Stale attempts updating progress / final manifests / publication pointers.
- Bucket-wide credentials or Drive publication credentials on workers.
- Reusing scratch while an old process may still write.
- Deleting by filename, `source_id` alone, or an unvalidated client prefix.

## Cutover (not this PR)

1. Write new jobs with namespaced keys; keep reading legacy keys via the job record.
2. Copy-on-read legacy objects into `tenants/{tenant}/jobs/{job}/inputs/…`.
3. Stop minting Drive tokens for workers; control plane stages inputs and publishes outputs.
4. Optional SQLite for publication journal; `job.json` remains the snapshot.
