# TikTok diversity screen — 2026-08-25

Jeff dropped six TikTok downloads in Lab Studio (count-1 Generate by
accident). Job `30246f9971c7` on workspace `ws_6152e4dffc` was
**cancelled** after the sources were copied. Do not use those count-1
outputs as a look test.

All six are **576×1024**, TikTok watermark in the corner. Not the
Instagram 720 SKU. Watermarked TikToks are fine for ranking clip class.
They are not look sign-off, TikFusion calibration, or a live pin.

Harness: `python scripts/first_pass_screen.py /tmp/vf-tiktok-div`
(medium, seed 42) on `7dae269`.

| Clip (what it is) | Dur | Shot label | Bits | 24? |
|---|---|---|---|---|
| Backyard UGC / grill (`export_1787647547954`) | 39s | motion | **40** | yes |
| Indoor close-up, emotional (`d7425l7`) | 27s | motion | **32** | yes |
| **Car talking/singing** (`d9r9iuf`) | 25s | motion | **21** | **no** |
| Night dance, three people (`d9vrt6v`) | 18s | motion | **33** | yes |
| Store dance, three people (`da3i9af`) | 45s | motion | **43** | yes |
| Solo outdoor dance (`da4t2t7`) | 14s | talking_head* | **51** | yes |

\*Classifier miss: 25%/75% self-bits were 16 so it labeled talking-head.
It is a dance. Crop used the 720-TH keep band; bits inflated. Do not
treat 51 as “talking-head is easy on 576.”

**5 / 6** clear 24 on encode 1.

The miss (car, 21 bits / 33% UI) is the same class as girlies: medium
under, **strong 24 / ok** in 12s. Fail-forward returns a file. Not
AQMTp (tight 720 face that stays 17–21 even on strong).

## What this does *not* change

- Do not retune Fast from watermarked 576 TikToks.
- Do not raise the 24-bit gate.
- Instagram 720 talking-head uniqueness hole is still **AQMTp**.
- Need a few **IG saves** (720, no TikTok logo) for look: another tight
  face, stickers, dance, UGC, 30–45s.

Lab Fast 8 of the IG SKU (same day, `7dae269`, warm): SaveInta **5.3 min
8/8 medium 25–26 bits**; AQMTp **5.3 min 8/8 strong 17–21 bits**, files
returned. Live Fast still `856e23d`.
