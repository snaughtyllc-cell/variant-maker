# Fast look-first shot probe (Smart Repurpose analog, not a detector)

**Date:** 2026-08-21  
**Status:** Shipped on lab and promoted to live Fast (`06526b9`, digest-pinned)  
**Product name:** VaryForge  
**Depends on:** `2026-08-21-fast-rebuild-scale.md`

## Why

One medium recipe cannot treat a talking-head like a running cinematic shot.
Uniqueness is SSIM at 576×1024. Motion already disagrees with itself; a stable
face does not. TikFusion Smart Repurpose consistency is look-first: classify
the shot, then pick a recipe. We do the same with ffmpeg, not OpenCV, and not
a platform detector.

Rebuild-scale (`4880c35`) left passing clips at **38–47%**. Copy still says
typical medium **55–65%**. Lab `06526b9` talking-head landed all-medium
**40/40/40 bits (62%)**, VMAF **98**, crop 0.84–0.88, caption upright. That
digest is now pinned on live Fast (`j0b1q4iuunzhnq`). Lab
(`xar25v77v3j27u`, `VF_LAB=1`) stays the experiment floor.

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
crop + chroma 40/56 scored **35/43 bits (55/67% UI)**. Lab `57aec3e` medium
copy 1: **40 bits (62.5%)**, VMAF **98**, caption upright. Copies 2–3
escalated to strong because ffmpeg noise seed defaults to `-1` (same pattern
→ peer bits 16–17). Per-copy `c1_seed`/`c2_seed` from the variant seed did
**not** lift peer above 13–14. Strong then used crop 0.78 (the face-zoom we
banned) and chroma 50–57 — still 13–14 peer bits. Talking-head therefore
**does not peer-escalate**; vs-source 24/24 still gates, peer bits are
recorded, `MIN_PEER_BITS` stays 24. Motion still uses the peer floor.
Lab `b6c2c9c` all-medium pack: chroma 40/45/48 → **40/43/44 bits (62/67/69%)**,
VMAF 98. Copy says typical **55–65%**, so medium chroma is **34–42**
(lab chroma 40 = 62%). Quality proxy still includes grain. Motion keeps luma
`alls=…:allf=t+u`. No extra rotate (captions).

| preset | default rebuild | talking_head rebuild | talking_head chroma grain | motion rebuild |
|---|---|---|---|---|
| medium | 0.67–0.80 | **0.90–0.98** | **34–42** | 0.78–0.90 |
| strong | 0.50–0.66 | **0.85–0.94** | **46–58** | 0.67–0.80 |
| subtle | 0.90–0.98 | 0.94–0.99 | 24–36 | 0.94–0.99 |

Missing file / ffmpeg miss → `shot=None` (do not crash the pack). HQ still
strips rebuild. Fast still never face-protects (Haar must not zero crop).

## Promoted (`06526b9`)

Lab talking-head job `77bfac36`: shot `{kind: talking_head, self_bits: 17}`,
all medium **40/40/40 bits (62%)**, VMAF **98.16 / 98.39 / 98.60**, crop
0.88 / 0.88 / 0.84, chroma `c1s=39`, rotate 0, `status=ok`, no escalate,
~22 MB under the 12M cap. Caption upright; shoulders in frame.

Lab motion job `9141c13e`: shot motion, self_bits 49, **51–52 bits (~80%)**,
VMAF 97.5–100, peer 50–52, luma `alls=7`.

Live Fast template `ka043gryih` and lab template `876soa0cd2` both pin
`ghcr.io/snaughtyllc-cell/variant-fast@sha256:8e0e0bbe8662fef5d161d16eb84ff5ad5ae4df6a99c66114753567326a233712`.
Live: `VF_ENGINE_REV=06526b9`, no `VF_LAB`, max 2, idle 600.
Lab: same rev, `VF_LAB=1`, max 1, idle 120.
Railway `RUNPOD_FAST_ENDPOINT_ID` stays `j0b1q4iuunzhnq`. Next experiments
stay on lab — do not PATCH live to test.

Look (not uniqueness): chroma noise used to run *after* the 720→1080
upscale, so a 720p Instagram talking-head got 1080-sized glitter. Chroma
band stays **34–42** (gate 24/24). Noise now runs after crop, before
platform scale, so speckles scale with the frame. Luma motion grain still
sits at the end of the graph.

Live verify (same sources on `j0b1q4iuunzhnq`): talking-head **39/39/39 bits
(61%)**, VMAF **97.5 / 98.8 / 98.6**, crop 0.86–0.88, caption upright.
Motion **53/51/51 bits (~80–83%)**, VMAF 100.

## Do not

- Raise `TARGET_BITS` / `MIN_PEER_BITS`
- Clone Pixel AI scramble
- Run OpenCV / `protect` on Fast
- Fake uniqueness %
- Point production Railway Fast at the lab endpoint
- Recycle live workers to test a lab digest
