# Fast reconstructive rebuild-scale (visible uniqueness, not Pixel AI scramble)

**Date:** 2026-08-21  
**Status:** In progress (engine)  
**Product name:** VaryForge  
**Depends on:** `2026-08-21-medium-crop-grain.md`, `2026-08-20-medium-pixel-seed.md`

## Symptom

Talking-head Fast packs scored **25–33%** uniqueness (below the ~38% pass line)
with 8/8 escalate. ±32 px resample is invisible at the uniqueness probe
(SSIM at **576×1024**, 3 frames). Face-only crop (0.74–0.82) scored *worse*
(16–20 bits). Unbudgeted warp pushed VMAF to **53–80** → `best_effort` →
harvest skipped the files, so Drive got 2–3 of 8.

Copy still says typical medium **55–65%**. Pass stays ~38% (24 bits).

## What this is / is not

Fast analog of a reconstructive round-trip (HQ's Real-ESRGAN cousin):
**downscale to ~540–864 then back to 1080×1920** with a seeded kernel.

Do **not** clone TikFusion Pixel Manipulation AI (scramble / DCT / odd size /
secret noise / named Smart Colors / fps jitter). Do **not** raise the gate.

## Change

| Axis | Was (crop-grain pack) | Now |
|---|---|---|
| medium `rebuild_scale` | (none; ±8–32 px) | **0.67–0.80** (~720–864 → 1080×1920) |
| strong `rebuild_scale` | (none) | **0.50–0.66** (~540–720). `strong.hi < medium.lo` so escalate is a heavier rebuild |
| subtle `rebuild_scale` | (none) | 0.90–0.98 |
| `warp_k1` | unbudgeted fingerprint | **budgeted** again (VMAF can shrink it) |
| medium crop / grain | 0.84–0.90 / 7–12 | unchanged |
| social maxrate | 12M | unchanged |
| gate | **24 / 24** | unchanged |

`sample()` draws `rebuild_scale` unbudgeted + `resample_flags` ∈ {lanczos, spline, bicubic}.
`resample_px` is still drawn as a leftover; filtergraph prefers rebuild and only
emits ±px when rebuild is identity.

Filtergraph after the platform even-scale:

```
scale={rw}:{rh}:flags={kernel},scale=1080:1920:flags={kernel}
```

`platform=none` (VMAF proxy): no rebuild. `_QUALITY_NEUTRAL` sets
`rebuild_scale: 1.0` and `resample_px: 0`. Warp stays in the quality render.

HQ `disable_fast_pixel_ops` sets `rebuild_scale=1.0`, `resample_px=0`, `warp_k1=0.0`.

## Why warp is budgeted again

Unbudgeted `warp_k1` on talking-head scored VMAF 53–80. `passes_guard` failed,
pipeline marked `best_effort`, `_uploadable` skipped those files. Rebuild is
the uniqueness lever the 576×1024 frame can see; warp is a look axis VMAF
must be allowed to cap.

## Do not

- Raise `TARGET_BITS` / `MIN_PEER_BITS` (stay **24 / 24**)
- Fake uniqueness %
- Skip VMAF or turn escalate off
- Face-only crop
- Clone Pixel AI scramble
- `railway up` / volume-swap Studio while Watch is generating
