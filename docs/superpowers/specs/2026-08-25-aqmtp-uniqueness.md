# AQMTp uniqueness loop — tight 720 talking-head

**Date:** 2026-08-25  
**Product:** VaryForge  
**Depends on:** `2026-08-25-ig-720-fast-20.md`, `docs/ops/first-pass-screen-2026-08-25.md`

## Symptom

Instagram 720 Fast 20 wait-time is shipped (`7dae269`). The remaining SKU
hole is a **tight still face that already fills the frame**. SnapInsta
AQMTp 720 talking-head scored **18 bits** on signed medium in the
first-pass screen — crop cannot buy uniqueness on that still. Fail-forward
returns the files in two encodes; they stay `below_target`.

SaveInta 720 (looser talking-head, same signed look) already clears 24 on
encode 1. Do not retune medium to “fix” AQMTp and lose that look.

## What we will not do

- Raise `TARGET_BITS` / `MIN_PEER_BITS` (stay **24 / 24**)
- Face-zoom crop `0.72` / `0.78`
- Pixel AI scramble / DCT / odd size
- Snow 720: chroma cloud **18–22**, luma dust **14–20**, phone-safe `c1s=27`
- Put talking-head on reconstructive rebuild `0.67–0.80` to buy bits
- PATCH live Fast / set `VF_LAB` on live
- Color that is not zero-mean (systematic desat/darken)
- Fast face-protect (HQ-only)

## What we learned (this session)

Lossless frames, then x264. Clip: SnapInsta AQMTp 720.

| Recipe | Bits |
|---|---|
| Crop-only keep **0.86 / 0.82** | **≈14–15** |
| Source self-bits | **18** |
| Signed medium (crop + cloud **4–7** + dust **11–13**) | **≈18–19** lossless, **18** full encode |
| + warp / hue / clarity / vignette / low-freq chroma | **+0–3** on a face-filling still |
| High-amp **mid-freq** luma shade | looks like a cookie / mesh — **rejected** |
| Low-freq luma shade **8×14**, `gblur=12`, `c0s` **90–100**, stacked on crop+cloud+dust | lossless **24** |
| same, **veryfast** x264 | `c90` smoothed to **22–23**; `c100` + cloud **7** + dust **13** scored **24** ok |
| **libx264 `-preset medium`** (engine, seed 42/1) | shade **95.6** + cloud **4.8** + dust **11.5**, gblur 12 → **22** |
| same engine, pin shade **100** + cloud **7** + dust **13**, gblur 12 | **23** |
| same pin, **gblur 10** (or 8) | **24** ok |

Warp, hue, clarity, vignette, and low-freq chroma do not move SSIM on a
still that already fills 576×1024. Crop on this clip is weaker than the
first-pass 17-bit note (keep 0.90/0.86/0.82) — this session’s crop-only
draw is **14–15**. Medium still lands **18**, same as the screen. Remapping
shade from grain onto `94–100` left escalate at the low end of that band;
pin the surviving caps. `gblur=12` still lost 1 bit to medium-preset x264.

## Change

1. **Medium 720 talking-head stays shade-off.** That is the signed SaveInta
   look (cloud 4–7 + dust 11–13). AQMTp will miss 24 on encode 1. Expected.
2. **Strong escalate draws `luma_shade`.** Same uniqueness loop as IG-720
   Fast 20 (`FAST_TUNE_MAX_ITERS = 1`): one medium, then one strong. Pins
   shade **100**, cloud **7**, dust **13** (no extra RNG), **phone canvas
   only** (short side < 1080), talking-head only.
3. **Filtergraph:** gray noise at **1/90** size (720×1280 → **8×14**),
   `gblur=sigma=10`, blend on **Y**. Strength **cap 100** so leftover
   cannot redraw a cookie mesh.
4. **HQ** `disable_fast_pixel_ops` zeros `luma_shade` (ESRGAN already
   rebuilds pixels).
5. **Quality proxy** strips `luma_shade` like crop (`_QUALITY_NEUTRAL`).
   VMAF must not `best_effort` the escalate.

Gate stays **24 / 24**. Fast still never face-protects. Color stays
zero-mean. `sample` and `filtergraph.build_*` stay pure.

## Already in

| Module | Owns |
|---|---|
| `variant_maker/shot.py` | `luma_shade_range_for_shot` (strong 720 TH only) |
| `variant_maker/sampler.py` | remap from grain; `disable_fast_pixel_ops` zeros shade |
| `variant_maker/filtergraph.py` | `_luma_shade_graph` |
| `variant_maker/quality.py` | `_QUALITY_NEUTRAL` `luma_shade: 0` |
| tests | `test_shot`, `test_sampler`, `test_filtergraph`, `test_quality` |

## Lab sign-off — do not pin live

Lab Fast 8 of **AQMTp** is the look sign-off. SaveInta 720 is the look
control: medium copies must still be shade-off.

Do **not** pin live from this spec. Live Fast stays `7dae269` /
`sha256:5f815e72…`, **no `VF_LAB`**, until Jeff signs the AQMTp pack.
Ops: `docs/ops/aqmtp-uniqueness-2026-08-25.md`.
