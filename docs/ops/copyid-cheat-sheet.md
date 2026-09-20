# CopyID cheat sheet (lab)

Local scores vs the flag we actually got. **Not** a platform predictor and
**not** a spoofing recipe. `platform_result` stays the oracle.

## What flagged

Jeff 2026-09-20: **duplicate / unoriginal**, not music / copyright.

That is a visual copy-id miss, not an audio fingerprint miss. Do not start
with Demucs stem-swap. Uniform `atempo` 0.96–1.04 is locked to video speed
and is not an audio lever.

## What we score today

| Dial | What it is | What it is not |
|---|---|---|
| `ssim_bits_v1` (gate **24** / ~38% UI, floor 19) | 3 frames at 576×1024 (orientation-aware). Grain, crop, chroma show up here. | Platform copy-id. Raising 24 does not clear duplicate/unoriginal. |
| Chromaprint `fpcalc` (`record` on lab Fast) | Landmark audio near-dupe. Needs **identity re-encode vs unrelated** on the **flagged clip** before a 0.7x sim means anything. | A music-copyright check. Same soundtrack will always match. |
| SSCD / DINO visual head | Learned embeddings over 8 frames, short-side 288. Slim Fast has no weights → `available: false`. | Meta production copy-id. Tau 0.75 is a starting guess. |

Grain and 576-canvas “uniqueness” typically **die by ~224px**. A 224×224 SSIM
proxy is in `copyid.calibrate.platform_proxy_canvas`. Do not buy bits with
shade, 720 snow, face-zoom, or Pixel scramble — look already rejected those.

## Do not keep using the old talking-head look packs

SaveInta / AQMTp / bring-me-down (LOOK, DRIFT, compete) were **look and SSIM
gate** clips. They are **not** the files getting duplicate/unoriginal now.
Do not pull them up again as the uniqueness failure sample. Do not retune
presets, CopyID tau, or Chromaprint floors from those packs.

Calibrate on the **clip that was flagged**: source vs an identity re-encode
vs an unrelated file of similar length.

```python
from variant_maker.copyid.calibrate import calibrate_paths
print(calibrate_paths("src.mp4", "reencode.mp4", "unrelated.mp4"))
```

`separates` on a head means that head can tell a re-encode from a different
video. Mid-band Chromaprint (both controls ~0.74–0.77) is **collapsed**, not
a uniqueness score.

## What we will not do this pass

- Raise `TARGET_BITS` 24
- `copyid=gate` (identical audio would fail overnight)
- PATCH live Fast (lab `record` only)
- Shade / 720 snow / face-zoom / Pixel AI scramble
- Stem-swap as the first build (wrong flag type)

## Next visual lever (not this PR)

**Intercut** (aligned-span B-roll / still / title card) — cheap structure
change for duplicate/unoriginal. Piecewise ±3% speed is a later fork against
the one-speed-factor invariant. Cover / first-frame is cheap. Flip is dead.

Heads must actually land on Fast: `ffmpeg` → wav → `fpcalc` (Debian libav
cannot open our BtbN mp4s); autotune must keep `quality.heads`.
