# CopyID cheat sheet (lab)

Local scores vs the flag we actually got. **Not** a platform predictor and
**not** a spoofing recipe. `platform_result` stays the oracle.

## What flagged

Jeff 2026-09-20: **duplicate / unoriginal**, not music / copyright.

That is a visual copy-id miss, not an audio fingerprint miss. Do not start
with Demucs stem-swap. Uniform `atempo` 0.96–1.04 is locked to video speed
and is not an audio lever.

Jeff 2026-09-20: the product is an **unchanged video** posted **again on
the same account** (another try). Same shots, same order. Intercut / B-roll /
freeze insert / title card is a recut — off.

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

## First flagged pair (2026-09-20, Drive `Flagged test`)

Not the old talking-head look packs. Same source, two Fast copies:

- `A56531F9-…_v15_bd60ad9d.mp4` and `…_v16_0e3f8e2d.mp4` (pipeline names:
  `{stem}_v{index}_{seed}.mp4`)
- Original HEVC 1080×1920 ~6s. Both copies **pass** local 24 (30 / 28 bits).
  Peer 27. At 224px they collapse (20 / 17 vs source, **14** peer).
- Burned-in title **Home can wait** is in the original and unchanged on both
  copies (same shots, same order — product).
- Jeff: the **text names** are damn near the same. Two signals: that overlay,
  and the engine filename stem. Repurpose/Buffer use the Drive filename as
  the post caption (`web/lib/howTo.ts`).

The product **is** posting this again on the same account without recutting.
v15 vs v16 flagged is the miss: local 24 passed, the platform still saw a
copy. Jeff: this is **not the only source** — another source keeps flagging
too. Same class, not a one-pack fluke. Do not rewrite **Home can wait**.
Do not raise 24. Distinct filenames/captions on export are not a video
change — sequential `UUID_v15` / `UUID_v16` names are an extra same-post
signal. Fable: that is a side channel, not the cause. Fix it; do not expect
it to clear the flag.

## What we will not do this pass

- Raise `TARGET_BITS` 24
- `copyid=gate` (identical audio would fail overnight)
- PATCH live Fast (lab `record` only)
- Shade / 720 snow / face-zoom / Pixel AI scramble
- Stem-swap as the first build (wrong flag type)
- Intercut / B-roll / freeze insert / title card (recut; not this product)
- Piecewise speed (same video to the eye, zero on this flag, fake local bits)
- Cover / first-frame (thumbnail only; copy-id samples the whole clip)
- Canvas reframe / letterbox (Meta lists aspect-ratio borders as immaterial;
  also a visible framing change)

## Fable 2026-09-20 (same-account retry, multiple sources)

Polish-only variants **cannot** pass this class. Fast medium (crop, rotate,
grain, warp, rebuild, speed, trim, fresh encode) is Meta's "immaterial edits"
list and the detector's training augmentations. Local 24 green + 224px
collapse is the same property from both sides. Multiple sources flagging is
the dial at ceiling, not a per-clip recipe miss. **No new engine transform
for this flag.**

Remaining:

1. **Ops (only plausible movement):** archive the original (and the flagged
   retry) before the next try, or wait until the original is no longer
   "relatively new." Studio does not automate account actions. Label
   `platform_result`. If that retry still flags, the class is closed on the
   oracle.
2. **Caption/filename hygiene (side channel, do now):** stop exporting
   `{UUID}_v{NN}_{seed}` as the Repurpose caption. Expect **zero** flag
   movement.
3. Encode identity, stronger polish, cover, canvas reframe: **kill** as
   levers for this flag.

Heads must actually land on Fast: `ffmpeg` → wav → `fpcalc` (Debian libav
cannot open our BtbN mp4s); autotune must keep `quality.heads`.
