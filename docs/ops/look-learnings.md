# Look + uniqueness learnings

**Read this before changing a 720/1080 recipe.** Bits and VMAF are not a look
check. Jeff’s eye (source vs variant stills) is the oracle. Append a row the
same day as the pack — do not bury a verdict in a session ops note.

Platform flags after a drop stay in Phase 12
(`docs/superpowers/specs/2026-08-18-platform-outcome-learning.md`) — that is
“did IG take it down,” not “does this still look like a real video.”

## How to log

1. Extract stills at a few timestamps. **Look at them** next to source.
2. Add a row: **Signed** / **Usable (under gate)** / **Rejected** / **Open**.
3. Do not retry a **Rejected** row to buy uniqueness bits.
4. Do not pin live until **Signed**.
5. Engine look-first (`variant_maker/look.py`) is a blotch backstop, not a
   substitute for stills. `lookaqmtp` is why it exists.

## Signed (keep)

| When | Clip / pack | Recipe | Bits / VMAF | Look |
|---|---|---|---|---|
| 2026-08-22 | SaveInta 720 TH `cleargate24a` / `13cd292` | Medium: crop 0.86–0.90 from top, chroma cloud **4–7** `gblur=4`, luma dust **11–13**. No shade. | 26/28 bits, VMAF 96–98 | **Yea ship it.** Live pin later `7dae269`. |
| 2026-08-22 | 1080 talking-head | Chroma grain **34–42** on 1080 pixels | ~40 bits (62%), VMAF 98 | 55–65% uniqueness band. Do not clone onto 720. |
| 2026-08-24 | Caption-word 1080 `wordcrop856e` | keep **0.92–0.96**, x/y 0.35–0.65 | 38/42 bits, VMAF ~100 | **yea way better** than keep 0.84 eating a word. |
| 2026-08-25 | SaveInta Fast 8/20 `7dae269` | Same signed medium. Fail-forward uniqueness. | 25–27 bits, all medium | Wait-time shipped. Was live Fast. |
| **2026-08-26** | SaveInta lab Fast 8 `472ab60` / live Fast 2 smoke | Stills overlap uniqueness; MAE after SSIM | **25–27 bits**, all medium. Lab 8 worker **3.1 min** (prior live uniqueness-only 8 was **4.2 min**) | Stills look like source. MAE can still trip on crop — stills are the oracle. **Shipped live** (`sha256:e7474975…`, no `VF_LAB`). |
| 2026-08-25 | SaveInta lab `looksaveinta` / `4540720` | Medium, **shade-off** | 24–27 bits, VMAF 95–99 | Control pack. Do not put shade on medium. |
| **2026-08-29** | Compete Fast `d0a7bc5` Gallery **LOOK-SaveInta** / **LOOK-AQMTp** / **LOOK-bring-me-down** (`166cf4bae4be`) | Rotate + vignette + per-copy 30/48/60. Medium. | **33/32**, **20/19**, **45/46** | **Jeff: yea they look fine.** AQMTp escalate-on under-19 parked (nose-close). **Shipped live** (`sha256:a5b703fa…`, **no `VF_LAB`**). |

## Usable (look OK, uniqueness under 24)

| When | Clip / pack | Recipe | Bits | Note |
|---|---|---|---|---|
| 2026-08-22 | SaveInta `quietdustmed` | dust 8–12, c0s=9 | **23** | Jeff: **that's usable.** Under gate. |
| 2026-08-25 | AQMTp medium (first-pass / shade-off) | Signed 720 medium | **18** | Tight face fills 576. Files look like the source. Gate miss is uniqueness-hard, not look-hard. |
| **2026-08-26** | AQMTp Gallery `lookshadeoff` / `21ae9d3` (`AQMTp-720.mp4`) | Shade-off 720 TH. Medium cloud 4–7 + dust 11–13; strong pins 7/13. **No shade.** | **17–21** | Jeff: **yea it looks good just scored low.** Do not pin. Do not redraw shade. |
| **2026-08-26** | Lab Fast `f05d803` AQMTp escalate (`aqmtpfloor`) | Same signed shade-off recipe. Strong after 24 miss. | **19/19** | Ships as `below_target` (30% floor). Not a uniqueness hunt. |

## Rejected (do not redraw)

| When | Clip / pack | Recipe | Bits / VMAF | Why |
|---|---|---|---|---|
| 2026-08-22 | 720 TH | phone-safe **c1s=27** / chroma 40 unsmoothed | 37 bits (58%) | **720 snow.** 55% on a still 720 face is this. |
| 2026-08-22 | `650f28dfb1f2` | stacked phone grain + cloud **18–22** | high | Snow on the face. |
| 2026-08-22 | `6d3e91ab7fd4` | cloud-only **18–22** | 40–43 bits | Still grain on the face. |
| 2026-08-22 | Live SaveInta `looktest4c41` | cloud **6–10** + `gblur=2` | — | Chroma a bit noticeable. Cap cloud at **7**, gblur **4**. |
| 2026-08-22 | `softdust815a` | dust **14–20**, c0s 15–17 | 25/26 | **grain a little much.** Cap dust at **13**. |
| 2026-08-22 | luma grain **40–52** | talking-head luma | 37–39 bits, VMAF **80** | `best_effort`. Harvest skipped. |
| — | face-zoom crop **0.72 / 0.78** | — | — | Banned. Strong 720 keep stays ≥ **0.82**. |
| — | talking-head rebuild **0.67–0.80** | — | bits drop | Lanczos smooths chroma 576 was scoring. |
| — | Pixel AI scramble / DCT / odd size | — | — | Not this product. |
| — | mid-freq luma shade / **16×28** cookie | — | — | Mesh on the face. |
| **2026-08-25** | **`lookaqmtp`** / `lab8_aqmtp454_68054751` / `4540720` | Strong 720 TH: luma shade **8×14**, `gblur=10`, **c0s=100**, cloud 7, dust 13 | **33–34 bits**, VMAF **97–99** | **Lava / oil-slick blotches on the face.** Jeff: visually shit. VMAF never saw the shade (quality proxy strips it). Coarse luma MAE **41–57** vs signed medium **12–32**. Do not redraw. Do not pin live. |

## Open

| Hole | What we know | What we will not do |
|---|---|---|
| AQMTp-class tight 720 talking-head that already fills 576 | **Parked.** Unusual nose-close crop; most uploads will not look like this. Jeff signed shade-off look (`lookshadeoff`, 17–21 bits). Compete escalate-on `9ba1af34f29d` was 18/17 — Jeff 2026-08-29: not a pin blocker. | Raise the 24 gate. Snow. Face-zoom. Shade/cookie. Build an escalate-rollback just for this clip. |

## Engine backstop

`variant_maker/look.py` (`coarse_luma_v1`): 16×28 luma MAE, max of 3 frames, fail if **> 38**. Stills land on the Generate card as soon as the first encode exists; two JPEGs overlap uniqueness SSIM so Generate wait stays uniqueness-bound. MAE is a blotch backstop **after** uniqueness (do not run it beside 8-wide SSIM — that contended Fast CPU). Crop on a signed talking-head can trip MAE even when the stills look fine; Jeff’s eye on the stills is the oracle, not the red/green. Look fail still blocks escalate. `look_mae` in the UI is the **mean**; the gate uses **max** (`look_mae_max`). Copy 1 of `lookshadeoff` is why: mean 36, max 77, status fail.

**19 bits / ~30%** is the *post-hunt* ship floor, not a first-pass shortcut: hunt 24 (medium, then one escalate). After that, 19–23 still ship. Under 19 is `uniqueness_fail` (not Drive-ready). TikFusion’s published floor is ~18 / ~28%. Live Fast is `d0a7bc5` (`sha256:a5b703fa…`, **no `VF_LAB`**). Prior live `f05d803` (`sha256:00564ea3…`). Writeup: `docs/ops/live-pin-d0a7bc5-2026-08-29.md`.

Leftover `luma_shade` params must not draw. Filtergraph ignores them.
