# Look-safe keyframe crop drift (start→end pan)

**Date:** 2026-08-28  
**Status:** Handheld wander on `cursor/crop-drift-live-cdb6`, stacked on compete
axes (rotate / vignette / per-copy 30/48/60). Jeff 2026-08-29: **build it on
live Fast.** Lab verify `1fbe4f51de83` vs LOOK `166cf4bae4be` — **live stays
`c497505`.** Not Gemini.  
**Product name:** VaryForge / varimo Studio  
**Depends on:** `2026-08-24-caption-safe-crop.md`, `2026-08-25-ig-720-fast-20.md`,
`2026-08-21-fast-shot-probe.md`, `2026-08-25-look-first.md`  
**Prior lab branch:** `cursor/keyframe-crop-drift-cdb6` (PR #56) — feat commits
`23862e8` + `bc88da1`. Do not cherry-pick that branch's lab-ops pins.

## Symptom

Today’s crop is one window for the whole clip: `crop_keep` + `crop_x_frac` /
`crop_y_frac`. Uniqueness (`ssim_bits_v1`) samples **3 frames at 25% / 50% /
75%**. A static punch shows the **same patch** at all three stamps. A tight
720 talking-head that already fills 576 still sits ~18 bits on signed medium
(AQMTp). Grain/shade were the bits we already rejected (`lookaqmtp` lava;
720 snow).

The next honest geometry is a **look-safe start→end pan** — an adjustment
layer over the existing punch: keep stays put, the window **micro-drifts**.
25 / 50 / 75 then see **different patches**. Later copy-detection Chamfer
(Phase 17 on the copyid branch: SSCD over a frame sequence) reads the same
idea: those stamps are different crops of the source. That is a local
tuning dial, not a platform verdict.

## What we will not do

- Gemini / any LLM on **variants** (or 20 vision calls per pack)
- Wait on the source-catalog producer (`2026-08-28-source-catalog.md`) —
  v1 uses the `shot.py` slot we already have
- Face-zoom crop `0.72` / `0.78`
- Ken Burns zoom (animated `crop_keep`) — v1 is pan only
- Raise `TARGET_BITS` / `MIN_PEER_BITS` (stay **24 / 24**)
- Skip VMAF, histogram, or look-first to chase bits
- Pixel AI scramble / DCT / odd size / shade overlays
- Drop compete axes (rotate / vignette / `out_fps`) to land the pan
- Consume the main or extra RNG for drift (trim / resample / vignette / fps
  must stay seed-stable)

## Change

**Adjustment layer.** Same crop filter, same keep. `x` / `y` lerp from start
fracs → end fracs over remaining duration (`t` after `setpts=PTS-STARTPTS`).
Compete axes stay after crop (eq → hue → vignette → unsharp → grain → fps).

| Axis | Rule |
|---|---|
| `crop_x_frac` / `crop_y_frac` | Start. Same bands as today. Main RNG. Same seed → **same start** as now. |
| `crop_x_end_frac` / `crop_y_end_frac` | End. **Separate RNG** (`seed ^ 0xC0DE5`) — resample / GOP / trim_end / vignette / `out_fps` stay put. |
| Keep | Unchanged. Still unbudgeted. 720 TH remaps via `crop_keep_range_for_shot`. |
| 1080 x/y | **0.35–0.65** start *and* end (caption-safe center, zero-mean at 0.5). |
| Instagram 720 y | **0.90–1.00** start *and* end — leftover from the **top**, burned-in words stay. x stays 0.35–0.65. |
| Max delta | **talking_head 0.24**; else **0.28** (`motion` or `shot=None`). Per axis, then clamp into the band. |
| Min X travel | **talking_head 0.08**; else **0.10**. `ensure_crop_travel` pushes end so the window actually moves (v1 could land on start — Jeff barely saw it). Y has no floor (720 band is only 0.10). |
| Handheld | Separate-RNG `crop_hand_amp_x` / `crop_hand_amp_y` / `crop_hand_p1` / `crop_hand_p2`. Talking-head amp **0.02–0.06** x, **0.005–0.016** y; else **0.028–0.070** / **0.010–0.028**. Periods **1.5–3.6s** and a slower second sine. |
| Budget | End fracs + handheld unbudgeted. `total_distortion` unchanged. |

The first lab pack (linear lerp, no floor, max 0.12) read as almost-static
with a few hard pixel steps. Destination is **handheld footage**: a slow
composition drift plus a two-sine wander, never a stair-step.

### Filtergraph

`crop` `w`/`h` stay constant (ffmpeg evaluates size once). `x`/`y` are
expressions. Commas inside `min`/`max` **must be escaped** (`\,`) so they
are not filter separators. Linear `t` + integer crop x/y is the hard shift
— use **smoothstep** `s = p*p*(3-2*p)` and a **2× scale** around the crop
so 1px steps become half-pixels and get filtered on the way back down:

```
p = min(max(t/D\,0)\,1)
s = p*p*(3-2*p)
xf = min(max(X0+(X1-X0)*s + AX*(sin(2*PI*t/P1)+0.4*sin(2*PI*t/P2))\,XLO)\,XHI)
scale=trunc(iw/2)*4:trunc(ih/2)*4, crop=iw*K:ih*K:(iw-iw*K)*xf:(ih-ih*K)*yf, scale=trunc(iw/2)*2:trunc(ih/2)*2
```

`D` = remaining duration after head/tail trim (`duration_s - trim_s -
trim_end_s`, floored to a tiny epsilon). Missing `*_end` and zero handheld
→ today’s static crop (existing goldens). `crop_keep ≈ 1` still omits crop.
720 y start/end ± amp stay in **0.90–1.00** (filtergraph also clamps the
expression). No extra rotate on talking-head — captions stay upright.

`sample` and `filtergraph.build_*` stay **pure**.

### Quality / look floors stay

- `_QUALITY_NEUTRAL` sets start **and** end fracs to `0.5`, handheld amps
  to `0`, keep `1.0`, vignette `0`, `out_fps` None so the VMAF proxy stays
  geometry-aligned. Do not VMAF the pan.
- Look-first (`look.py`, coarse 16×28 luma MAE, max of the same 25/50/75)
  scores the **actual** file. Crop already can trip MAE; Jeff’s eye on the
  stills is the oracle. Look fail still blocks escalate.
- Histogram wash-out check stays on the quality proxy.

### Uniqueness check (why the pan exists)

1. **Now — 3-frame SSIM** at 25 / 50 / 75 (`FRAME_FRACS`). A pan means those
   frames are different source patches. Bits may move. Gate stays 24/24.
2. **Later — copy-detection Chamfer** (SSCD / DINOv2 over a frame sequence,
   min-fused; default `off` on Fast). Open the 25 / 50 / 75 stills and
   **see different patches**. SSCD is crop-robust by design — Chamfer rise is
   not the ship gate. Evidence the window moved, not a platform pass.

AQMTp-class faces that already fill 576 may still miss 24. Fail-forward
still returns the pack. Do not buy those bits with shade or snow. That clip
is parked.

### Slot for the catalog (do not wait)

v1 reads `shot=` + canvas the way `sample` already does. A later producer
(`2026-08-28-source-catalog.md`) writes the same pinpoints — kind, caption
band, safe `pan_x` / `pan_y` / zoom — and sampler clamps into that envelope.
**Swap the producer, not the lerp.** Heuristic v1 is enough to prove the pan
on a pack.

## Already in (do not regress)

| Module | Owns |
|---|---|
| `sampler.py` | Start `crop_*_frac`; 1080 0.35–0.65; 720 y 0.90–1.00; compete vignette / `out_fps` on extra RNG |
| `shot.py` | `talking_head` vs `motion`; 720 TH keep; `keeps_bottom_captions` |
| `filtergraph.py` | Static crop golden when ends missing/equal; compete rotate / vignette / fps after crop |
| `quality.py` | `_QUALITY_NEUTRAL` keep 1.0, x/y 0.5, vignette 0, `out_fps` None |
| `look.py` | Actual-output MAE at 25/50/75 |

## Do not

- Raise the uniqueness gate
- Gemini on each variant
- Animate keep / zoom in this phase
- Face-protect Fast (HQ still clamps keep, not a pan)
- Set `VF_LAB` on live Fast
- Change production `RUNPOD_FAST_ENDPOINT_ID`
