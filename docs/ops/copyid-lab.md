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

Lab Fast `xar25v77v3j27u` image 2026-08-31: digest `sha256:e8d77b9f…` /
`21691c4` (record audio off uniqueness wait) / `VF_LAB=1` /
`VARIANT_MAKER_COPYID=record` / max 1. Pack `c701c9fb3594` **audio
scored** `via=ffmpeg_s16le` on every copy. Stay **`record`**. Prior
`sha256:caa55785…` / `c1af220`. Live Fast is `sha256:e8d77b9f…` / `21691c4` /
no copyid / no `VF_LAB`. Do not `gate`.

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
   NEW pack `6f506c681f8b` was the same (`reason: error`) even after a wav
   fallback existed — `_fpcalc` tried **direct first**. Fix: **wav-first**
   (`pcm_s16le` @ 11025), empty fingerprint is a miss, then direct. Visual
   stays `available: false` on slim Fast (no torch/SSCD). Stay **`record`**.

Do **not** treat this pack as a copyid verdict. Re-run after the lab image
rebuild. Stay on **`record`**. Do not `gate`. Do not PATCH live.

### Lab Generate — pack `5ef63612aaf3` (look stills + crop-align MAE)

Same three NEW clips. Image `sha256:1d0a9753…` / `f0651b8`. Fast 2, escalate on,
`quality_mode=fast`. Lab tenant only. Live untouched.

| Clip | Copy | SSIM bits | Look MAE (max) | Audio |
|---|---|---|---|---|
| NEW-0409 | 1 / 2 | **41 / 41** medium `ok` | **ok/ok** 4.33/3.0 (max 6/4) | `reason: error` |
| NEW-1277 | 1 / 2 | **33 / 31** medium `ok` | **ok/ok** 7.0/3.67 (max 10/4) | `reason: error` |
| NEW-bradnded | 1 / 2 | **32 / 31** medium `ok` | **ok/ok** 4.0/4.67 (max 5/6) | `reason: error` |

Look MAE is the win: brad was **119/84** on `6f506c681f8b` (keyframe seek +
caption crop). Gate **38** unchanged. Gallery stills use `still_vf` zscale;
agent stills are not olive (white wall / grey shirt / skin). Jeff’s eye is
still the look oracle.

**Audio still missed.** `copyid=record` wrote heads. Visual `available: false`
(no SSCD — expected). Audio `reason: error` with no `via` on every copy.
This box scores the same source+variant files `via=ffmpeg_s16le` /
`sim` 0.66 / 0.73 / 0.81. Wav-first still handed a `.wav` to Debian
`fpcalc` (same libav that cannot demux BtbN mp4s).

### Lab Generate — pack `bd19fcc20eed` (raw s16le image `4bd8a57`)

Same three NEW clips. Image `sha256:113a9dec…`. Fast 2. Look still **ok**
(MAE max 8/13, 4/9, 14/4). Audio every copy: `reason: error` /
`detail: CalledProcessError: ERROR: Error decoding audio frame (End of file)`.
Debian `fpcalc -format s16le` treats raw PCM EOF as a failed frame. Next
image: stdlib `wave` header (duration known) + if FINGERPRINT= printed,
use it even on exit 1. Stay **`record`**. Do not `gate`. Do not PATCH live.

### Lab Generate — pack `ce6862e51d4c` (classic WAV `c1af220`)

Same three NEW clips. Image `sha256:caa55785…`. Fast 2. First job after
recycle (`1bf301c5711a`) 500'd on cold start; this retry delivered 6/6.

| Clip | Bits | Look MAE (max) | Audio sim | Audio uniq |
|---|---|---|---|---|
| NEW-0409 | **45 / 43** medium `ok` | **ok/ok** 6.67/5.0 (11/7) | 0.82 / 0.83 | 0.18 / 0.17 |
| NEW-1277 | **32 / 31** medium `ok` | **ok/ok** 2.33/4.0 (3/5) | 0.68 / 0.72 | 0.32 / 0.28 |
| NEW-bradnded | **35 / 30** medium `ok` | **ok/ok** 5.0/6.33 (6/9) | 0.82 / 0.83 | 0.18 / 0.17 |

Every copy `heads.audio.available: true` `via=ffmpeg_s16le`. Visual still
`available: false` (no SSCD). **If this had been `gate`, every copy fails**
on audio (uniq ~11–20 bits). Stay **`record`**. Do not `gate`. Do not
PATCH live. Jeff stills remain the look oracle.

Scoring that audio sat on the uniqueness thread (~20 s extra on copy 1 vs
the EOF miss). Source was decoded again for every copy. Engine change on
`cursor/copyid-audio-speed-6cba`: prefetch source Chromaprint during encode,
cache the fingerprint for later copies, SSIM-only uniqueness wait for
`record`, fingerprint the **kept** file after MAE (not every autotune
attempt). `gate` still fuses inside uniqueness. Live stays `off`.

### Lab Generate — pack `c701c9fb3594` (`21691c4` speed)

Same three NEW clips. Image `sha256:e8d77b9f…` / `VF_ENGINE_REV=21691c4`.
Fast 2, escalate on, `quality_mode=fast`. Lab tenant only. Recycled lab
Fast only. Live verified `e7ab2cc` / no `VF_LAB` / copyid off.

Created `2026-08-31T08:00:51Z`, done `08:21:19Z` (~20.5 min including
~2 min cold start). Uniqueness events fire after SSIM, before Chromaprint
on the kept file.

| Clip | Bits | Look MAE (max) | Audio sim | Audio uniq |
|---|---|---|---|---|
| NEW-0409 | **43 / 44** medium `ok` | **ok/ok** 4.67/2.67 (8/3) | 0.76 / 0.85 | 0.24 / 0.15 |
| NEW-1277 | **34 / 31** medium `ok` | **ok/ok** 4.0/5.33 (5/8) | 0.70 / 0.82 | 0.30 / 0.18 |
| NEW-bradnded | **32 / 32** medium `ok` | **ok/ok** 2.67/6.0 (3/7) | 0.92 / 0.89 | 0.08 / 0.11 |

Every copy `heads.audio.available: true` `via=ffmpeg_s16le`. Visual
`available: false`. Brad MAE is crop-align, not lava. **If this had been
`gate`, every copy fails** (brad audio uniq ~5–7 bits). Stay **`record`**.
Do not `gate`. Do not PATCH live. Jeff stills remain the look oracle.

**Wall clock vs SaveInta Fast 8 (~5 min for 8):** this pack is **3 sources
queued on 1 lab worker**, two of them ~1 min 1080 (0409 is 1920×1080 65s,
1277 1080×1920 63s, brad 22s 60fps). Encode is the 20 min. Chromaprint is
seconds after SSIM, not the extra 15 min. A SaveInta Fast 8 is one short
720 talking-head × 8 in parallel on a worker sized for 8 x264s.

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
