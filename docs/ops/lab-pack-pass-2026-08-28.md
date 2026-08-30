# Lab pack pass — compete Fast — 2026-08-28

Lab Fast only (`xar25v77v3j27u`, `d0a7bc5`, `VF_LAB=1`). Live Fast
`j0b1q4iuunzhnq` / `f05d803` was not patched. Production Studio was
read-only (clip copy). Writes went to lab tenant `ws_6152e4dffc`.

Gallery: https://varyforge-studio-lab.up.railway.app

## What ran

Fresh Fast 2 through lab Studio (real product path, not injected
`look*` folders). Plus today’s live daily clips pulled off production.

| Job | Clip | Role |
|---|---|---|
| `0c5e1614c991` | SaveInta-720 | control TH, escalate on |
| `9ba1af34f29d` | AQMTp-720 | tight TH, escalate **on** |
| `6e8d2e9adc8d` | AQMTp-720 | tight TH, escalate **off** |
| `b665383756f8` | eyes-color | live daily 720 TH |
| `246f78865ef8` | nothing-can-bring-me-down | live daily 720 motion |
| `85a763a04640` | hot-girl-summer | live daily 720 selfie |
| `186f139bce7d` | pucci | live daily 720 fashion |
| `b8188b15b6a3` | guess-what-happens-next | live daily 720 fashion |
| `821596ce9f50` | tulum-lagoon | live daily 720 lifestyle |
| `469b6d9f97ed` | girlies | lab motion |
| `99ed217e0af5` | win-chat | lab motion |
| `709af898ac80` | SaveInta2-720 | short lab motion |
| **`166cf4bae4be`** | **LOOK-SaveInta / LOOK-AQMTp / LOOK-bring-me-down** | uniquely named Sign pack, escalate **off** |

Earlier same-day injected `lookcompete4` is still in Gallery (Jeff’s
first compete look). Do not confuse it with the API jobs above.
The Sign pack is the three **LOOK-** cards at the top of lab Gallery.

## Bits

| Pack | v1 | v2 | Escalate | Look | Notes |
|---|---:|---:|---|---|---|
| **SaveInta esc on** | **31 ok** | **31 ok** | no | ok / ok | 60 / 60 fps, vig 0.11, rot +0.35 |
| **AQMTp esc on** | **18 fail** | **17 fail** | **yes** (strong) | ok / ok | under 19 after hunt — not Gallery |
| **AQMTp esc off** | **19 below_target** | **21 below_target** | no | ok / fail | **19 ships**; v2 look-fail |
| eyes-color | 39 | 38 | no | fail / ok | live |
| bring-me-down | 45 | 45 | no | ok / ok | live motion; 48 + 30 fps |
| hot-girl-summer | 36 | 35 | no | fail / fail | live |
| pucci | 34 | 36 | no | ok / fail | live; both 60 fps |
| guess-next | 33 | 35 | no | fail / ok | live |
| tulum | 34 | 34 | no | fail / fail | live |
| girlies | 27 | 30 | no | ok / ok | 48 + 60 fps |
| win-chat | 30 | 28 | no | fail / fail | 48 + 60 fps |
| SaveInta2 | 34 | 34 | no | ok / fail | |
| **LOOK-SaveInta** | **33 ok** | **32 ok** | no | fail / fail MAE | Jeff signed stills |
| **LOOK-AQMTp** | **20 ok** | **19 ok** | no | ok / ok | 19 ships |
| **LOOK-bring-me-down** | **45 ok** | **46 ok** | no | ok / ok | |

Every non-AQMTp copy cleared 24. AQMTp stayed uniqueness-hard.

## Floor check

- **19 ships:** AQMTp escalate-off v01 (`6e8d2e9adc8d`) is `below_target`
  / `status=ok` at 19 bits, look-ok. In Gallery.
- **Under 19 fails:** AQMTp escalate-on both copies hunted (strong),
  still **18 / 17**, `uniqueness_fail`, **0 delivered**. Diagnostics
  only. Floor did its job.
- Escalate-on did **not** recreate the old `f05d803` “strong → 19 ship”
  path on this seed. Strong + tighter keep (0.84–0.86) + vig 0.16 on
  v02 did not buy bits.

Do not raise 24/24. Do not redraw shade.

## 48 / 60 fps + audio

Per-copy 30 / 48 / 60 all showed up. Audio `start_time=0` on both
streams; A/V duration within ~0.03–0.10 s (trim, not drift). One
`speed` on video and audio (SaveInta v01 speed 0.978 both).

| Copy | fps | A/V |
|---|---|---|
| SaveInta both | 60 | locked |
| AQMTp esc-off | 30 / 48 | locked |
| girlies | 48 / 60 | locked |
| bring-me-down | 48 / 30 | locked |
| win-chat | 48 / 60 | locked |
| pucci both | 60 | locked |

Play the 48/60 files in Gallery if you want motion, not just stills.

## Captions + face (25 / 50 / 75)

AQMTp mid-frame caption *“then why don't you just let me help you?”*
is fully in-frame on source and both escalate-off copies. Rotate
±0.35° does not clip letters. Punch-in (keep ~0.87) eats margin, not
words. Face is the source’s tight selfie, not a new cheap tilt.

SaveInta this seed has **no burned-in caption** in the stills. Face
reads like the source; 60 fps + vig ~0.11 still passed look-ok.

`lookcompete4` SaveInta v01 (vig 0.114, 48 fps) was look-fail —
black-corner vignette. Fresh SaveInta both look-ok. girlies
lookcompete4 was look-fail; fresh girlies both look-ok.

Look MAE is not the oracle. Several live copies trip MAE 100+ from
crop (eyes v01, hot-girl, guess, tulum) and still look like the
source in Gallery. Jeff stills decide.

## Crop-drift

Not run. Handheld / crop-pan stay on draft branches. Compete look
is signed on `LOOK-*`. Do not swap lab Fast to a crop-drift digest
as part of this pin decision.

## Look Sign (2026-08-29)

Jeff on the uniquely named Sign pack (`166cf4bae4be`): **yea they look
fine.** Cards: `LOOK-SaveInta.mp4`, `LOOK-AQMTp.mp4`,
`LOOK-bring-me-down.mp4`. That is the look oracle. MAE look-fail on
LOOK-SaveInta does not override.

## Live pin

Look is signed. Jeff **parked** the AQMTp escalate-on under-19 as a
blocker (2026-08-29): the clip is super-close face-to-camera, not the
average upload. Do not build an escalate-rollback just for that SKU.
Do not raise 24. Do not redraw shade.

Live Fast stays `j0b1q4iuunzhnq` / `f05d803` / no `VF_LAB` until Jeff
says pin compete (`d0a7bc5`) onto live.
