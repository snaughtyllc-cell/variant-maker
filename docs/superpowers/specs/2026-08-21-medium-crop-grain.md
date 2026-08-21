# Medium crop punch + modest grain (score up, files down)

**Date:** 2026-08-21
**Status:** In progress (engine)
**Product name:** VaryForge
**Depends on:** `2026-08-20-medium-uniqueness-delivery.md`, `2026-08-20-medium-pixel-seed.md`, `2026-08-20-fast-social-bitrate-cap.md`

## Symptom

A Fast talking-head pack (Strata → Jeff, 8 copies, pixel seed on) landed:

| Clip | Uniq | esc | Size |
|---|---|---|---|
| high-motion | 81% | 0/8 | ~20 MB / 19 Mbps |
| talking-head | 37–50% | 0 or 8/8 | 11–17 MB, **or 65–111 MB / 65 Mbps** on all-esc |

Copy still says typical medium **55–65%**. Pass is ~38% (24 bits). Two all-`esc` batches wrote ~65 Mbps files from 1–3 MB Instagram downloads.

Pixel seed (`resample_px` ±8–32, `warp_k1` ±0.015) was already in the encode. It did not move talking-head SSIM at 576×1024. The 12M social cap was in git but warm Fast workers had not pulled it.

## Causes

1. **Crop still too timid.** Medium keep `0.86–0.94` is a 6–14% punch-in. `crop_keep≈0.858` on escalate still scored **24 bits (~38%)** on the worst talking-head. Crop is the vs-source uniqueness lever; resample ±32 px is nearly invisible at the SSIM size.
2. **Strong grain 14–22 at unconstrained CRF.** Temporal `noise=alls=` is a weak SSIM lever and a huge bitrate bomb. libx264 wrote ~65 Mbps at 1080×1920. The 12M cap stops the ceiling; grain should not sit there.

## Change

| Axis | Was | Now |
|---|---|---|
| medium `crop_keep` | 0.86–0.94 | **0.74–0.82** (always ≥18% punch) |
| strong `crop_keep` | 0.80–0.92 | **0.66–0.74** (escalate hi ≤ medium lo) |
| medium `grain` | 7–14 | **4–8** |
| strong `grain` | 14–22 | **6–10** |
| social maxrate | 12M (already shipped) | unchanged — must actually be in Fast `ffmpeg_cmd` |
| Fast pixel seed | resample ±8–32, warp ±0.015 | unchanged |
| gate | **24 / 24** | unchanged |

Do **not** raise `TARGET_BITS` / `MIN_PEER_BITS`. Do **not** skip VMAF. Do **not** turn escalate off. Do **not** clone TikFusion Pixel Manipulation AI scramble. Color stays zero-mean. `sample` / `filtergraph` stay pure.

HQ still face-protects (Fast never clamps crop). 18–26% punch-in on Fast talking-head is the uniqueness look — a different camera, not a 3% peek.

## Copy

Pass line remains ~38%. Typical medium remains **55–65%**. `esc` is still not a fail. Huge Drive files were grain + missing maxrate, not uniqueness %.
