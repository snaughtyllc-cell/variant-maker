# Fast idle / scale-to-zero (Wave 2 ops)

**Date:** 2026-09-05  
**Status:** Encode — dashboard settings + in-process rules. Primer is **off** until measured.  
**Product name:** VaryForge  
**Depends on:** occupancy router (`docs/superpowers/specs/2026-08-20-after-sales-tracks.md` Wave 1). This slice does **not** ship a primer job, reconstruct-first, or a second HQ GPU.

Astra’s contract for interactive Fast wait: start with **min=0, max=2, FlashBoot where supported, and a short idle timeout**. A morning primer only if it reliably precedes real use. A primer shifts cold-start wait earlier; it does not guarantee warm capacity later.

## Frozen

- Color correctness, VMAF floor, uniqueness **24 vs source / 24 vs peers**.
- Do not split one 20-pack across two machines.
- Min workers stay **0**. Do not buy always-on Fast CPU, extra endpoints solely for warming, always-on GPU, or keep-alive jobs that purchase continuous CPU.
- Reconstruct-first and HQ GPU occupancy are **out of this slice**.

## 1. Idle and scale-to-zero

Fast CPU endpoint (RunPod dashboard, not code):

| Setting | Value |
|---|---|
| Min workers | **0** |
| Max workers | **2** (matches two occupancy slots; one complete pack per worker) |
| Idle timeout | **120 seconds** as the first experiment. Adjust from measured gaps between interactive requests. Production today is 600s — this is a trial, not an automatic cutover. |
| FlashBoot | On where the CPU endpoint supports it. Verify on that endpoint. [Endpoint settings](https://docs.runpod.io/serverless/endpoints/endpoint-configurations) |

Overnight: keep min=0, disable primers and keep-alive, let both workers expire after their last real job. Fast compute reaches **$0** once both stop. Unfinished real jobs continue. Storage and the Railway router may still cost money.

In-process slot states (`variant_maker/server/fast_idle.py`, `occupancy_journal.py`):

| State | Meaning |
|---|---|
| Occupied | A job is reserved, starting, executing, uploading, or stopping after cancellation. Keep the slot. |
| Idle | No reservation; processes and uploads have ended; cleanup is complete. Start the idle timer. |
| Unknown | Heartbeat lost or lease expired, but termination is unconfirmed. Reconcile with RunPod before reusing the slot. |

**Missing heartbeats or expired leases do not prove idleness.** A healthy idle worker can still send health heartbeats; those must **not** reset the idle timer. Only actual work (`work_start`, `work_progress`, `upload`, `cleanup`) resets it.

## 2. Morning primer — do not ship yet

First measure **FlashBoot + the idle timeout alone**. Trial a primer only if the first interactive request still suffers **and** its arrival is predictable.

When (later) enabled:

- Trigger from an operator **start session** action, or one scheduled request shortly before a known session.
- One small synthetic item on the real Fast FFmpeg path. Three items have no clear warming benefit unless measurement shows otherwise.
- `kind=primer`, system-owned job id, isolated scratch, **no** studio manifest, **no** Drive publish.
- At most one primer globally. Start only when no real job is queued and no worker is already warm or starting.
- Reserve a normal occupancy slot atomically. It counts toward max=2 but **does not** occupy a studio’s one-job lock.
- Expiry: discard if it cannot start promptly. Never repeat it to hold capacity forever.
- The real request must arrive before the warmed worker’s idle timeout. Idle retention is billable. [Runpod billing](https://docs.runpod.io/flash/pricing)

`should_start_primer(..., primer_enabled=False)` returns `"disabled"`. Do not add a cron or keep-alive.

## 3. Real job vs primer (when primer exists)

Real work always wins:

| Primer state | Action |
|---|---|
| Queued, not submitted | Remove it; reserve the slot for real work. |
| Worker booting | Mark superseded. Hand the real job to that worker if the dispatch protocol allows; otherwise stop the primer at the first safe checkpoint. |
| Encoding | Cooperatively cancel, stop subprocesses, confirm cleanup, then release. Reuse the warm worker where supported. |

If the other slot is free, real work may start there immediately and the unnecessary primer stops. Do not assume cancelling a RunPod request keeps its worker — measure that.

A primer must never leave a real 20-pack waiting behind a 1-item warm-up. Packs do not move between concurrent machines.

## 4. Do not buy yet

- Always-on Fast CPU.
- Extra Fast endpoints solely for warming.
- Always-on GPU.
- Repeated keep-alive jobs.
- A second HQ GPU pool (Wave 3 — skipped until Fast is no longer the queue).

A bounded warm window later only if measured interactive demand justifies idle cost.

## 5. Metrics

Log on the job and copy onto `usage.jsonl` when present:

| Metric | Detail |
|---|---|
| Start classification | `cold` / `warm` / `unknown`; worker id and boot id. FlashBoot evidence is a **separate** field (often unavailable). |
| Startup breakdown | Router queue, provider queue, image pull, boot/init, handler-ready. Mark missing stages `null`. |
| Time-to-first-output | Request received → first accepted item. Report count=1, count=2, and count=20 separately. |
| Pack completion | Request received → requested items ready (download or Drive). |
| Worker billing | Billed seconds split into real work, primer work, and idle retention where measurable. |
| Primer usefulness | (When primer exists) completion → real arrival gap, worker reuse, cancel, unused expiry, real-job delay caused by primer. |

Compare p50/p95 interactive latency and billed minutes across **FlashBoot alone**, **FlashBoot + idle retention**, and **the same plus primer**.

Helpers: `classify_start`, `billed_parts` in `fast_idle.py`. `record_job` persists `start_class`, `startup`, `billed`, `first_output_utc` when the job telemetry includes them.

## 6. Restart journal (no Redis)

One process, in-memory occupancy, mutex around reservations. Persist `{DATA_DIR}/fast_occupancy.json` (`OccupancyJournal`):

- Slot, tenant id, job id, attempt id, fencing token, provider job id, worker/boot ids.
- On router restart: **pause dispatch**, mark occupied slots **unknown**, list RunPod jobs, then reconcile.
- Provider still running → occupied. Provider confirms gone → idle. Untracked running job or unknown without a provider id → stay paused; do not treat the slot as free.

Without this journal, a restart can lose occupancy and allow a second pack for a studio that is already running. Redis is not required.

## Not this

- Reconstruct-first GPU prep vs Fast slot (not launching).
- HQ GPU occupancy / second 4090.
- Uniqueness or VMAF changes.
- Always-on anything.
- Shipping the primer job in this PR.
