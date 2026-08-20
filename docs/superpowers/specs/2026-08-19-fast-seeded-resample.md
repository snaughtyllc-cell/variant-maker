# Fast seeded resample (TikFusion Random Pixels, without weird output size)

**Date:** 2026-08-19  
**Status:** Shipped on Fast (resample + encode-first look shrink + `warp_k1` pixel seed).  
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
Fast pixel seed is a tiny zero-mean `lenscorrection` (`warp_k1`), VMAF-capped.

## Scope

| In | Out |
|---|---|
| Fast only (`quality_mode=fast`), Reels/TikTok/Shorts (platform has w×h) | HQ (ESRGAN already rebuilds pixels — `disable_fast_pixel_ops`) |
| `sample()` draws unbudgeted `resample_*` plus budgeted zero-mean `warp_k1` | Changing uniqueness gates (stay **24 vs source, 24 vs peers**) |
| `filtergraph.build_video_filters` emits extra scales + lenscorrection | `platform=none` has no resample (quality proxy uses none) |
| Neutralize **resample** in `_QUALITY_NEUTRAL`; **keep warp** so VMAF caps it | Odd output size; fps 30–60 jitter; named film/vibrant looks |

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
3. **HQ skip** — `disable_fast_pixel_ops` zeros `resample_px` and `warp_k1` on HQ.
4. **Quality** — `resample_px: 0` in `_QUALITY_NEUTRAL`. `warp_k1` stays so VMAF
   can cap the pixel seed. Do not skip VMAF.
5. **Look shrink** — over-budget: grain/unsharp/crf first; color+crop+warp share
   what remains (both still show; still zero-mean).

## Not this

- Phase 12 (platform outcome learning)
- Raising `TARGET_BITS` / `MIN_PEER_BITS` again
- Always-on workers / splitting one pack across CPU+GPU
