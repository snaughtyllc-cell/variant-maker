# Fast: keep sub-1080 sources native, scale grain to the pixel grid

**Date:** 2026-08-22  
**Product name:** VaryForge  
**Depends on:** `2026-08-21-fast-shot-probe.md` (chroma-before-scale)

## Why

A 720×1280 Instagram talking-head was lanczos-scaled to 1080×1920 on Fast,
then given the 1080-calibrated chroma band **34–42**. ffmpeg `noise` is
per-pixel, so that is glitter — first from the naive upscale, then from
1080-strength grain on a 720 grid. HQ Real-ESRGAN is the true upscaler;
until that path runs, Fast must not invent 1080p.

Keeping 720p without touching grain would still look cheap: chroma 40 on
720p is the same glitter at native size.

## Change

1. **Fast only** (`quality_mode != hq` or Real-ESRGAN unavailable):
   `fit_platform_to_source`. If even source `w,h` already fit inside the
   social canvas (1080×1920), replace the platform size with the even
   source size. 4K still downscales. `none` is unchanged.
2. **Grain follows the grid it hits.** Sampler bands stay 1080-calibrated
   (talking-head medium **34–42**, motion luma **7–12**). `filtergraph`
   scales ffmpeg strength by `min(w,h) / 1080`, capped at 1.0.
   - Chroma (talking-head) hits the **source** grid (before platform scale)
     → 720p chroma 40 becomes **27**.
   - Luma (motion) hits the **output** canvas → 720p luma 8 becomes **5**.
3. HQ still targets **1080×1920** so Real-ESRGAN can upscale.

Gate **24/24** unchanged. Fast still never face-protects.

## Do not

- Raise `TARGET_BITS` / `MIN_PEER_BITS`
- Naive-upscale Fast “so the file is 1080”
- Apply 1080 chroma 34–42 on a 720 frame
- PATCH live Fast to test; rebuild the Fast image and pin the digest
