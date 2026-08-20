# Medium uniqueness delivery (50–60% typical, 38% pass)

**Date:** 2026-08-20  
**Status:** Shipped (engine + Studio copy)  
**Product name:** VaryForge

## Symptom

A Fast workflow of ~8 talking-head sources showed `esc` on every file. One batch
scored ~35% uniqueness. Medium is supposed to land in the **50–60%** band
comfortably.

## What those numbers mean

Gallery uniqueness is `round(bits / 64 * 100)`.

| UI | Bits | Meaning |
|---|---|---|
| ~35% | ~22 | Below the 24-bit **pass** (~38%). Medium never cleared vs the original. |
| ~38% | 24 | Pass line. Do not raise this gate to 32. |
| ~50–60% | 32–38 | What medium should **score** on talking-head. This is not a remapped scale. |

`esc` means medium + autotune missed vs-source (and/or 24-bit peers), so the
pipeline spent one strong pass. It is not a quality fail. A 35% tile **after**
escalate means even strong landed `below_target`.

Raising `TARGET_BITS` / `MIN_PEER_BITS` to 32 previously escalated entire Fast
20-packs. This change does **not** raise those floors and does **not** fake the %.

## Causes

1. **Face-protect on Fast.** `protect.apply_to_params` ran whenever OpenCV /
   MediaPipe was importable. Haar coverage ≥15% (typical talking-head) sets
   `crop_keep=1.0`. Crop is the vs-source uniqueness lever. Fast CPU images do
   not install OpenCV; the GPU image does. Fast fallback onto GPU (or any Fast
   worker with `cv2`) zeroed crop → ~22 bits + all-esc.
2. **Budget shrink ate crop.** `crop_keep` was budgeted. When color+warp
   overspent, `sample()` pulled keep toward 1.0. VMAF already ignores crop
   (`_QUALITY_NEUTRAL`), so shrinking it bought nothing for quality and killed
   uniqueness.
3. **Medium crop too timid** once keep actually applied (0.90–0.97). Talking-head
   SSIM at 576×1024 does not move 32 bits on a 3–10% punch-in.

## Fix

- `pipeline.use_face_protect` is **HQ-only**. Fast never grabs a protect frame
  and never clamps crop. HQ still face-gates so Real-ESRGAN does not punch into
  faces.
- `crop_keep` is **unbudgeted** (same class as resample / crop offset). Same seed
  → same keep at strength 0.25, 1.0, or 1.8.
- Medium crop `0.86–0.94`, warp `±0.012`. Strong stays `0.80–0.92` so escalate
  can still punch in harder.
- Gate stays **24 vs source / 24 vs peers**. Escalate stays on. VMAF stays on.

## Copy

Pass line remains ~38%. Hover / Advanced text says medium should land ~50–60%
and `esc` is the stronger encode after a miss — not a fail.
