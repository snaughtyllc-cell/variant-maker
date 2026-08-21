# Fast look-first shot probe (Smart Repurpose analog, not a detector)

**Date:** 2026-08-21  
**Status:** In progress (engine)  
**Product name:** VaryForge  
**Depends on:** `2026-08-21-fast-rebuild-scale.md`

## Why

One medium recipe cannot treat a talking-head like a running cinematic shot.
Uniqueness is SSIM at 576×1024. Motion already disagrees with itself; a stable
face does not. TikFusion Smart Repurpose consistency is look-first: classify
the shot, then pick a recipe. We do the same with ffmpeg, not OpenCV, and not
a platform detector.

Live after rebuild-scale (`4880c35`): clips that already passed 24 bits stayed
**38–47%**. The 16–21-bit talking-head has not been re-run. Copy still says
typical medium **55–65%**.

## Change

After `probe`, once per source:

1. Extract uniqueness-canvas frames at 25% and 75%.
2. `self_bits = bits_from_ssim(SSIM(those two frames))`.
3. `self_bits < 24` → `talking_head`; else → `motion`.
4. Pass `shot=` into `sample()` (pure). `shot=None` is today’s recipe.

Rebuild ranges (crop/warp unchanged; gate **24/24**). Lab AQMTp at rebuild
0.25–0.31 still scored 20–22 bits. A local sweep on that clip showed rebuild
0.27 = identity encode (8 bits) on the 576 canvas; crop 0.86 + `noise=alls=32/40/56`
scored **28/31/38 bits (44/48/59% UI)** under the 12M cap. Talking-head therefore keeps a *sharp* rebuild and remaps grain after the
draw, then budget/VMAF shrink toward shot.lo (not preset.lo). Lab grain 40–52
scored 37–39 bits (~58–61%) but VMAF ~80 (`best_effort`, harvest skip). Band
is 28–34 so the quality guard's VMAF ceiling stays reachable. No extra rotate (captions).

| preset | default rebuild | talking_head rebuild | talking_head grain | motion rebuild |
|---|---|---|---|---|
| medium | 0.67–0.80 | **0.90–0.98** | **28–34** | 0.78–0.90 |
| strong | 0.50–0.66 | **0.85–0.94** | **32–38** | 0.67–0.80 |
| subtle | 0.90–0.98 | 0.94–0.99 | 18–26 | 0.94–0.99 |

Missing file / ffmpeg miss → `shot=None` (do not crash the pack). HQ still
strips rebuild. Fast still never face-protects (Haar must not zero crop).

## Do not

- Raise `TARGET_BITS` / `MIN_PEER_BITS`
- Clone Pixel AI scramble
- Run OpenCV / `protect` on Fast
- Fake uniqueness %
