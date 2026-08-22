# 720 talking-head: usable look vs 55% uniqueness

**Date:** 2026-08-22  
**Product name:** VaryForge  
**Depends on:** `2026-08-22-fast-native-res.md`, `2026-08-21-fast-shot-probe.md`

## Symptom

SaveInta 720×1280 Fast (chroma sampler **on**, shot `talking_head`,
phone-safe c1s **13–15**) scored **41–48%**. Jeff: uniqueness used to sit
over 50%; now we are back under 50%; if chroma is already on, do we need
Pixel AI to get confidence back?

## What those numbers were buying

Gallery uniqueness is SSIM bits at **576×1024**, 3 frames. On a still face,
576 almost only sees **crop + chroma grain**. Lab 1080 talking-head chroma
34–42 scored **55–65%**. The same band on 720 is snow. After the 2.5
phone-scale, chroma 40 → **15**. That pack is **20/20 medium**, all above
the **38% / 24-bit** gate, no escalate.

Local SaveInta bench (crop 0.86, same encode):

| Recipe | 576 | Native 720 | 1080 canvas |
|---|---|---|---|
| Identity | 2 bits (3%) | 2 (3%) | 2 (3%) |
| Current (c1s=14, sharp rebuild) | **26 (41%)** | 25 (39%) | 22 (34%) |
| + rebuild 0.73 | 24 (38%) | 23 (36%) | 21 (33%) |
| + rebuild 0.67 | 24 (38%) | 22 (34%) | 20 (31%) |
| Old snow (c1s=27) | **37 (58%)** | 38 (59%) | 34 (53%) |

Chroma **is** on. 41–48% is that sampler at a strength that looks usable.
58% is the grain Jeff already rejected. Reconstructive rebuild **lowers**
bits (lanczos smooths the chroma 576 was scoring). Scoring at native 720
does not recover the 55% band.

## What we will not do

- Raise `TARGET_BITS` / `MIN_PEER_BITS` (stay **24 / 24**)
- Put talking-head on preset rebuild `0.67–0.80` to “buy” %
- Clone TikFusion Pixel Manipulation AI (scramble / DCT / odd size)
- Add 720 snow back so Gallery says 55–65%
- PATCH live Fast to test
- Split one pack across Fast and HQ

## What we do

- Keep phone-safe 720 grain. Keep chroma on for talking-head.
- Treat **~40–50% as a passing usable 720 Fast pack**. Pass stays 38%.
- 55–65% remains the **1080** talking-head band (chroma 34–42 on 1080 pixels).
- Studio copy says that so 41% is not read as a miss.
- True pixel rewrite without snow is **HQ Real-ESRGAN**, a separate pack —
  not Fast CPU, not Pixel AI scramble.

Gate **24/24** unchanged. Fast still never face-protects.
