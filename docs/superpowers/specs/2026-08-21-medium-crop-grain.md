# Medium uniqueness + file size (crop, grain, unbudgeted warp)

**Date:** 2026-08-21
**Status:** Shipped (crop/grain). Warp unbudgeted superseded by `2026-08-21-fast-rebuild-scale.md`.
**Product name:** VaryForge
**Depends on:** `2026-08-20-medium-uniqueness-delivery.md`, `2026-08-20-medium-pixel-seed.md`, `2026-08-20-fast-social-bitrate-cap.md`

## Symptom

A Fast talking-head pack (Strata → Jeff, 8 copies, pixel seed on) landed:

| Clip | Uniq | esc | Size |
|---|---|---|---|
| high-motion | 81% | 0/8 | ~20 MB / 19 Mbps |
| talking-head | 37–50% | 0 or 8/8 | 11–17 MB, **or 65–111 MB / 65 Mbps** on all-esc |

Copy still says typical medium **55–65%**. Pass is ~38% (24 bits). Two all-`esc` batches wrote ~65 Mbps files from 1–3 MB Instagram downloads.

## Live miss: face-only crop made scores *worse*

AQMTp re-encoded with keep `0.66–0.72`, grain `6`, warp budget-shrunk to `≈0.001`:

- Uniqueness **16–20 bits (25–31% UI)**, all `below_target`, all `esc`
- Files **9.4–11.1 MB / ~6 Mbps** (was 111 MB / 65 Mbps) — 12M cap works
- Same clip previously scored **24 bits (38%)** at keep `≈0.858` + grain 14–22

Punching a talking-head into a face-only zoom makes the 576×1024 SSIM frames look *more* alike (big face vs big face). Grain and warp were doing the uniqueness work; budget shrink zeroed warp on strong.

## Change

| Axis | Was (pixel-seed pack) | Face-only try | Now |
|---|---|---|---|
| medium `crop_keep` | 0.86–0.94 | 0.74–0.82 | **0.84–0.90** (always ≥10%, background stays) |
| strong `crop_keep` | 0.80–0.92 | 0.66–0.74 | **0.78–0.86** |
| medium `grain` | 7–14 | 4–8 | **7–12** (texture; 12M is the size ceiling) |
| strong `grain` | 14–22 | 6–10 | **10–16** |
| `warp_k1` | budgeted (often ≈0 on strong) | same | **unbudgeted** fingerprint, like crop |
| social maxrate | 12M in git | **on Fast cmds** | unchanged |
| gate | **24 / 24** | 24 | unchanged |

Do **not** raise `TARGET_BITS` / `MIN_PEER_BITS`. Do **not** skip VMAF. Do **not** turn escalate off. Do **not** clone TikFusion Pixel Manipulation AI scramble. Color stays zero-mean. `sample` / `filtergraph` stay pure.

HQ still face-protects (Fast never clamps crop). HQ still strips resample+warp.

## Copy

Pass line remains ~38%. Typical medium remains **55–65%**. `esc` is still not a fail. Huge Drive files were unconstrained CRF + grain, not uniqueness %.
