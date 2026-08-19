# Fast seeded resample (TikFusion Random Pixels, without weird output size)

**Date:** 2026-08-19  
**Status:** Parked — **do not build until Jeff says go.**  
**Product name:** VaryForge

## Why

TikFusion Smart Repurpose (Default / Medium / Smart Detector on) uses
**Pixel Manipulation AI** plus **Random Pixels** (jitter output size, keep AR).
HQ Real-ESRGAN is the reconstructive cousin of Pixel AI; it is too slow for a
Fast 20-pack. Fast already has grain (`noise=alls=…`) — that is the cheap
cousin; SSIM counts it, the eye reads a re-encode.

The Fast pixel thing we will ship (when asked) is a **seeded resample**, not
scramble and not a random output size:

1. After the Reels scale to 1080×1920, scale to a slightly different **even**
   size (AR kept, ~±4–16 px on width).
2. Scale back to **1080×1920** with a seeded kernel (`lanczos` / `spline` /
   `bicubic`).
3. Every pixel is a new sample. Instagram / Repurpose still get a normal Reel.
   Color stays zero-mean. VMAF floor stays.

Random **output** dimensions help a local file hash, then IG scales them away.
The leftover after ingest is the same as this round-trip. Shipping 1076×1912
is the part we skip (letterbox / Repurpose re-fit).

Do **not** copy Pixel Manipulation AI (secret noise / DCT / named Smart Colors).

## Scope

| In | Out |
|---|---|
| Fast only (`quality_mode=fast`), Reels/TikTok/Shorts (platform has w×h) | HQ (ESRGAN already rebuilds pixels — zero `resample_px`) |
| `sample()` draws unbudgeted fingerprint axes (like `crop_x_frac`) | Changing uniqueness gates (stay **32 vs source, 24 vs peers**) |
| `filtergraph.build_video_filters` emits the extra scales | `platform=none` (no extra scale; quality proxy uses none) |
| Neutralize in `_QUALITY_NEUTRAL` like crop | Odd output size; fps 30–60 jitter |

## Implementation contract (when unparked)

TDD. `sample` and `filtergraph.build_*` stay **pure**.

1. **Sampler** — each variant draws even `resample_px` from about ±4–16
   (never 0) and `resample_flags` ∈ {`lanczos`, `spline`, `bicubic`}. Same
   seed → same params. Unbudgeted (must not move `total_distortion`). Mix of
   smaller and larger intermediates so we do not systematically soften one way.
2. **Filtergraph** — after `even_scale_filter(target_w, target_h)`:
   `scale=W:H:flags=KERNEL,scale=TW:TH:flags=KERNEL` with `W,H` even, AR from
   the platform target. Omit when `resample_px` is missing/0. Sanitize flags
   (unknown → `lanczos`). Golden string tests; even-dim assert.
3. **HQ skip** — `pipeline` zeros `resample_px` on the HQ path so the
   neural-pre downscale render is not double-resampled.
4. **Quality** — add `resample_px: 0` to `_QUALITY_NEUTRAL`. Histogram + VMAF
   still gate the real file. Soft-looking output → strength comes down (existing
   guard). Do not skip VMAF.

## Not this

- Phase 12 (platform outcome learning)
- Raising `TARGET_BITS` / `MIN_PEER_BITS` again
- Always-on workers / splitting one pack across CPU+GPU
