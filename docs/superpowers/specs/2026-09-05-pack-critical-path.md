# Pack critical-path timing (Wave 2 measure)

**Date:** 2026-09-05  
**Product:** VaryForge  
**Status:** instrument now; do not buy primer / keep-alive / extra jobs until a labeled 20-pack report exists  
**Depends on:** uniqueness loop (24/24), Fast worker split, job telemetry  
**Plan note:** `docs/superpowers/specs/2026-08-20-after-sales-tracks.md` Wave 2

## Goal

Time a **full Fast 20-pack including rejected uniqueness candidates**. Timing only
the encode that shipped hides the hunt. SSIM 24 vs source and 24 vs peers stays.

This is measurement. It does not raise the gate, skip VMAF, split a pack across
machines, or turn HQ parallel.

## What to record

| Stage | Where | Measure |
|---|---|---|
| Startup | job telemetry | `submitted_utc` → `started_utc` → `first_render_utc` |
| Encode | `quality.hunt` per variant | wall per **candidate**, including rejects (`rejected_encode_s`) |
| Acceptance | same | `uniqueness_s` (vs source), `peer_s`, `quality_s`; `reject_reasons` (`source_ssim` / `peer_ssim` / `quality`) |
| Hunt | `run.hunt` + job `telemetry.hunt` | candidates, accepted, `attempts_per_accepted`, `by_slot` 1–N, `time_to_accept` |
| Delivery | job telemetry | leftover after startup + worker wall, if ≥ 5s (`upload_s`) |
| Cost | existing | `runpod_cost_usd` on billed seconds (retries included) |

Attach `worker_id`, `encode_jobs`, source duration/geometry (already on `source` snapshot), and pack `signature`.

Optional pack-level `cpu_s` / `maxrss_kb` from `getrusage` (Linux). Per-candidate CPU/IO waits on a later ops pass — wall + reject counts are enough to name the bottleneck.

## Signatures

| Signature | Read it when |
|---|---|
| `cold_start_bound` | Startup ≥ 20s and a large share of pack wall. Warm vs cold of the **same** clips. |
| `encode_bound` | Shipped encode time dominates; few rejected candidates. |
| `hunt_bound` | Attempts per accept ≥ 1.4 **or** rejected-encode + SSIM/peer time ≥ shipped encode. Watch slots 15–20. |
| `queue_or_upload_bound` | `upload_s` ≥ 20s and a large share of wall. Warming/concurrency barely help. |
| `mixed` | No single stage wins. |

Compare **cold and warm** runs of the same representative inputs. Repeat — hunt variance is real. Report pack latency **and** billed $ per completed 20-pack, including retries.

## Fix order (after the report, not before)

Do not budget morning primer and keep-alive as one option.

1. Morning primer — if cold start is the signature and demand is predictable. Failure: worker scales down, primer misses the real image, unused mornings cost money.
2. More Fast `jobs` on the **existing** worker — if CPU/memory/IO have spare capacity. Failure: x264 already fills cores; concurrent hunt races peers and wastes work. Recheck peers before commit (already locked). HQ stays serial.
3. Bounded keep-alive in the active window — if cold starts recur between nearby requests. Failure: ping may not keep the execution worker; idle billing; does not cut encode/hunt.
4. Business-hours warm CPU, scaled down after — if daytime demand makes idle $ worth it. Failure: quiet hours waste money; bursts above the warm baseline still cold-start.

If warm runs are already slow **and** the worker has spare capacity, trial concurrency **before** more warming.

Choose by **minutes off pack completion per added dollar**, plus $ per accepted 20-pack. None of these reduce uniqueness work.

## What we will not do in this slice

- Raise 24/24 or skip the quality floor
- Always-on GPU
- Split one 20-pack across CPU+GPU
- Clone another tool’s recipe
- PATCH live Fast as a timing experiment
