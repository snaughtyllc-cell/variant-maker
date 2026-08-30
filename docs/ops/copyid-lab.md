# CopyID lab — SSCD / Chromaprint / fused uniqueness

Local uniqueness heads that approximate copy detection. Not a platform verdict.

## Lab first (2026-08-29)

Jeff: **yes lab first.** Live Fast stays `copyid=off`. Do not PATCH live.

1. **`record` on lab Fast only** — score visual/audio heads, SSIM still gates
   (24/24 hunt, 19 floor). Identical audio must not fail a pack.
2. **`gate` later** — only after a labeled lab pack. Same-song clips would
   fail overnight if we fuse too early.
3. Fast CPU image has **`fpcalc`** (Chromaprint). SSCD/torch is not in the
   slim Fast image — visual head stays `available: false` there until a
   weights-capable worker. Score SSCD on a lab box with `COPYID_LAB=1`.

### First lab score — DRIFT pack `1fbe4f51de83` (record, 2026-08-29)

Same three clips as compete LOOK. `copyid=record` on this box (`fpcalc` 1.5.1).
SSIM bits match the Generate card. Visual skipped (no torch/SSCD).

| Clip | Copy | SSIM bits (gate) | Audio sim | Audio uniq (1−sim) |
|---|---|---|---|---|
| SaveInta | 1 / 2 | **33 / 33** `ok` | 0.74 / 0.77 | 0.26 / 0.23 (~17/15 bits) |
| AQMTp | 1 / 2 | **18 / 17** `below_floor` | 0.81 / 0.87 | 0.19 / 0.13 (~12/8 bits) |
| bring-me-down | 1 / 2 | **43 / 45** `ok` | 0.84 / 0.79 | 0.16 / 0.21 (~10/13 bits) |

**If this had been `gate`, every copy fails.** Same soundtrack → Chromaprint
still matches. SSIM can be 33/45 while audio uniq sits under the 19-bit
floor. That is why lab is `record` only. Do not turn `gate` on until we
decide what “different enough audio” means — not this week, not on live.

Lab Fast `xar25v77v3j27u` pinned 2026-08-29: digest `sha256:97544653…` /
`c709df0` / `VF_LAB=1` / `VARIANT_MAKER_COPYID=record` / max 1. Live
`j0b1q4iuunzhnq` left on `c497505` / no copyid / no `VF_LAB`.

### First lab Generate — pack `3d4fae98ca77` (2026-08-29)

Lab tenant `ws_6152e4dffc` only. Fast 2, escalate on, `quality_mode=fast`.
Worker **did** run `copyid=record` (`manifest.run.copyid`). Live untouched.

| Clip | Copy | SSIM bits (gate) | Heads written | Audio |
|---|---|---|---|---|
| SaveInta | 1 / 2 | **30 / 35** `ok` medium | **null / null** | — |
| AQMTp (parked) | 1 / 2 | **19** strong `below_target` / **21** medium `below_target` | **yes / null** | `available: false` |
| bring-me-down | 1 / 2 | **46 / 45** `ok` medium | **null / null** | — |

Two bugs, both on Fast daily path:

1. **Auto-tune dropped heads.** Fast reconstructs `u` from `tune()` with
   bits/status only. Medium copies (SaveInta, AQMTp 2, motion) wrote
   `quality.heads=null`. AQMTp copy 1 escalated → `_look_then_uniqueness()`
   kept the dict. Fix: pass `heads` / `copyid_mode` through that rebuild.
2. **Audio head never scored.** The one heads blob we got (AQMTp 1) is
   `chromaprint_v1` `available: false`. Image has `fpcalc` (`Dockerfile.fast`
   runs `fpcalc -version`) but Debian libav cannot open our BtbN mp4s.
   Fix: decode a 11.025 kHz wav with our ffmpeg, then `fpcalc` the wav.
   Visual stays `available: false` on slim Fast (no torch/SSCD).

Do **not** treat this pack as a copyid verdict. Re-run after the lab image
rebuild. Stay on **`record`**. Do not `gate`. Do not PATCH live.

## Enable record (lab) or the fused gate (later)

```bash
export VARIANT_MAKER_COPYID=record   # lab first — SSIM still gates
# export VARIANT_MAKER_COPYID=gate  # only after a labeled pack
# optional:
export VARIANT_MAKER_COPYID_VISUAL=auto   # sscd | dino | off | auto
export VARIANT_MAKER_SSCD_PATH=models/sscd/sscd_disc_mixup.torchscript.pt

variant-maker in.mp4 -n 2 --preset medium --copyid gate -o /tmp/copyid-out
```

`record` scores heads but **SSIM still drives** the ladder (safe on Fast 20).  
`gate` drives autotune/escalate from `min(ssim, visual, audio)`.

## Weights

SSCD (preferred visual head). Meta archived the repo; weights are TorchScript:

```
https://dl.fbaipublicfiles.com/sscd-copy-detection/sscd_disc_mixup.torchscript.pt
```

Save to `models/sscd/sscd_disc_mixup.torchscript.pt` (gitignored). Pin SHA256 in the lab log when you download.

DINOv2 fallback (no SSCD file): `facebook/dinov2-small` via transformers, CPU ok.

Audio: install Chromaprint `fpcalc` on PATH (`fpcalc -version`). Never hit AcoustID.

## Tests

```bash
# CI / this repo — no weights
pytest -q -m "not lab and not integration" tests/test_copyid_compare.py tests/test_copyid_fuse.py tests/test_copyid_chromaprint.py tests/test_copyid_visual.py tests/test_copyid_uniqueness.py tests/test_uniqueness.py

# Lab GPU/CPU box with weights + fpcalc
COPYID_LAB=1 pytest -q -m lab tests/test_copyid_lab.py
```

## What to log on a real pack

For each variant: `quality.heads.ssim.bits`, `heads.visual.sim`, `heads.audio.sim`, fused uniqueness, look MAE, then later `platform_result`. Retune SSCD tau (start 0.75) from those labels — do not copy TikFusion’s 35%.
