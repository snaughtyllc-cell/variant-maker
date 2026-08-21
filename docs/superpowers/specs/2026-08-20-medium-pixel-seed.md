# Medium Fast pixel seed (higher uniqueness, not Pixel AI scramble)

**Date:** 2026-08-20  
**Status:** Shipped (engine + Studio copy)  
**Product name:** VaryForge  
**Depends on:** `2026-08-19-fast-seeded-resample.md`, `2026-08-20-medium-uniqueness-delivery.md`

## Why

Medium uniqueness is SSIM bits (`bits/64*100`). Crop already lands talking-head
in the 50s when face-protect is off. The next honest lever is the Fast **pixel
seed** we already ship — not TikFusion Pixel Manipulation AI.

HQ Real-ESRGAN is the reconstructive cousin. Fast analog:

1. Seeded even resample round-trip back to 1080×1920 (Random Pixels leftover
   after Instagram scales away a weird file size — we skip shipping 1076×1912).
2. Zero-mean `lenscorrection` `warp_k1`, VMAF-capped.

Do **not** copy secret noise / DCT / named Smart Colors / fps jitter / scramble.

## Change

| Axis | Was | Now |
|---|---|---|
| `resample_px` | even ±2–16 | even **±8–32** (never 0, never a 2 px peek) |
| medium `warp_k1` | ±0.012 | **±0.015** |
| strong `warp_k1` | ±0.016 | **±0.020** (escalate still punches harder) |

Crop is now `0.74–0.82` medium (`2026-08-21-medium-crop-grain.md`). Gate stays **24 vs source / 24 vs peers**.
Escalate on. VMAF on. Color zero-mean. HQ still strips resample+warp.

## Copy

Typical medium ~**55–65%** (~35–42 bits). Pass line remains ~38%. `esc` is
still not a fail. This is not a remapped scale.
