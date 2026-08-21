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
0.27 = identity encode (8 bits) on the 576 canvas; crop 0.86 + luma
`noise=alls=32/40/56` scored **28/31/38 bits (44/48/59% UI)** under the 12M cap.
Talking-head therefore keeps a *sharp* rebuild and remaps grain after the draw.
Lab luma grain 40–52 scored 37–39 bits (~58–61%) but VMAF ~80 (`best_effort`,
harvest skip). Luma 28–34 passed VMAF 91 but only **42–47%**. SSIM All sees
chroma; VMAF is mostly luma. Talking-head grain is therefore chroma-only
(`noise=c0s=0:c1s=g:c2s=g`, `video.noise_chroma=true`, no extra RNG). Local
crop + chroma 40/56 scored **35/43 bits (55/67% UI)**. Medium band **38–50**
aims at typical 55–65%. Quality proxy still includes grain — lab must prove
VMAF ≥90. Motion keeps luma `alls=…:allf=t+u`. No extra rotate (captions).

| preset | default rebuild | talking_head rebuild | talking_head chroma grain | motion rebuild |
|---|---|---|---|---|
| medium | 0.67–0.80 | **0.90–0.98** | **38–50** | 0.78–0.90 |
| strong | 0.50–0.66 | **0.85–0.94** | **46–58** | 0.67–0.80 |
| subtle | 0.90–0.98 | 0.94–0.99 | 24–36 | 0.94–0.99 |

Missing file / ffmpeg miss → `shot=None` (do not crash the pack). HQ still
strips rebuild. Fast still never face-protects (Haar must not zero crop).

## Do not

- Raise `TARGET_BITS` / `MIN_PEER_BITS`
- Clone Pixel AI scramble
- Run OpenCV / `protect` on Fast
- Fake uniqueness %
