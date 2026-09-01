# HQ reconstruct-first + weekly usage + telemetry

**Date:** 2026-08-28  
**Product:** VaryForge Studio  
**Branch:** `cursor/hq-prep-weekly-usage-cdb6`  
**Base:** `tier1`  
**Depends on:** `2026-08-20-after-sales-tracks.md` Wave 6.2, HQ neural path already in `pipeline.py`

## Why

Jeff signed the compete-axes look for **lab** (PR #58). Next product tracks:

1. **HQ is not a 20-pack product.** One GPU reconstruct takes too long. The build is
   **one HQ pass, then Fast N** from that file — the step before the daily pack.
2. **Weekly usage** must survive the 7-day Gallery prune. Live queue Fast/HQ stays
   “who is generating now.” Week Fast / Week HQ is the ledger.
3. **Sentry + PostHog**, env-gated, no-op without keys. Server HTTP capture so
   npm/`sentry-sdk` stay optional.

Do **not** pin live Fast. Do **not** raise the 24-bit uniqueness gate.
Do **not** mix more Fast engine knobs into this PR (those stay on #58).

## HQ product shape

| | Standalone HQ 20-pack | Reconstruct-first (this) |
|---|---|---|
| GPU | 20 serial upscales | **1** upscale |
| Pack | HQ variants in Gallery | **Fast** variants in Gallery |
| `quality_mode` | `hq` | stays **`fast`** |
| `prep_mode` | `none` | **`hq`** |

Studio checkbox: **“Reconstruct first (HQ) — one GPU pass, then Fast variants.”**  
Not an HQ quality dropdown. The Advanced HQ option stays disabled.

Watch-folder **Workflows** use the same checkbox (`prep_mode=hq`, `quality_mode=fast`).
They do not run an HQ 20-pack.

API still accepts `quality_mode=hq` (tests / CLI). Studio Generate always sends
`quality_mode=fast` plus optional `prep_mode=hq`.

### Loop

1. HQ `count=1` into `{source}/prep/` — swallow variant events (no fake v01 slot).
2. Copy the ok hero to `{source}/in/prep_hq.mp4`.
3. Fast N from that file into the normal `out/` dir. Those are the Gallery copies.
4. HQ fail → that source does **not** silently Fast from the original. Skip Fast
   for that source; other sources continue.

Resume: if `prep_hq.mp4` already exists, skip HQ and Fast from it.  
Regenerate after an HQ-prep job also reads `prep_hq.mp4` when present.

Uniqueness after prep is scored vs the **reconstructed** file (the new master).
That is the uniqueness lift: Real-ESRGAN rewrote pixels, then Fast varies from
that — not more Fast scramble. Look stills vs the phone original may trip MAE;
Jeff’s stills stay the look oracle. Gate stays **24/24**.

## Weekly usage

`{workspace.root}/usage.jsonl` — one line per finished job, **outside** `jobs/`,
so Gallery prune cannot erase the week.

```
{"utc":"…Z","job_id":"…","fast_copies":20,"hq_preps":1,"packs":1,
 "prep_mode":"hq","quality_mode":"fast"}
```

- `fast_copies` — delivered ok variants when `quality_mode != hq`
- `hq_preps` — successful HQ reconstructs (`prep_mode=hq`), **or** delivered
  variants on a standalone `quality_mode=hq` pack
- `packs` — 1
- Idempotent on `job_id` (resume / finally must not double-count)
- Cancelled jobs are not recorded

Admin adds **Week Fast** / **Week HQ** (last 7 days UTC). Does **not** replace
live queue Fast / HQ.

## Telemetry

| Env | Role |
|---|---|
| `SENTRY_DSN` | Optional `sentry_sdk.init` (import-optional) |
| `POSTHOG_KEY` / `POSTHOG_API_KEY` | Server `/capture/` via urllib |
| `POSTHOG_HOST` | Default `https://us.i.posthog.com` |

No keys → no-op. Failures never raise into the job loop.  
Event: `job_completed` with job_id, prep_mode, quality_mode, counts.

## Out of scope

- Pin live Fast / merge #58
- HQ 20-pack UI
- Stripe / 30-day caps (PR #34)
- Raising uniqueness gate or Pixel-AI scramble
