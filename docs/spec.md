# variant-maker — Spec v0.2 (two-tier AI variant generator)

Local-first, CLI-first. One source video in → N rendered variants + a manifest out.
**Primary goal: a true variant generator** — outputs that read as real, original videos, not
degraded re-encodes. The variant maker is the deliverable; everything else is in service of it.

**Two tiers:**
- **Tier 1 — FFmpeg core (CPU, ships first, runs anywhere).** Correct color, controlled
  transforms, in-loop quality guard. This alone fixes the "1990s phone / washed-out" problem,
  because that problem is an engineering bug, not a missing AI feature.
- **Tier 2 — Neural layer (GPU, optional, the quality leap).** Reconstructive ops that change
  pixels *meaningfully while inventing plausible detail*, so variants look as good or better than
  the source while being statistically distinct.

> Changelog from v0.1: reframed around indistinguishable quality as the primary objective; added
> color-correctness (the real cause of wash-out), the VMAF/quality guard, the perceptual budget,
> and the full Tier-2 neural layer. The standalone "scorer/detector" is **out of scope** here (see
> bottom) — for now the platform you test on *is* the oracle.

---

## 0. What this is NOT (scope guards)

- **Not** a detector. A local "would-IG-catch-this" detector is a *later* improvement that distills
  test results into a fast local predictor. For now you test variants on the real platform and label
  them. The manifest's `platform_result` slot (below) is the only hook needed for that future work.
- **Not** an IG-spoofing engine. Beating a specific platform's detector is a separate concern layered
  on later. This project makes good, distinct variants and measures their quality.

---

## 1. Architecture

Single Python orchestrator. No queue/daemon for Tier 1. Per variant:

```
probe source (ffprobe: w/h, fps, duration, has_audio, COLOR tags) + sha256
load preset (subtle|medium|strong) + platform profile
for i in 1..count:
    variant_seed = derive(master_seed, i)            # deterministic
    params       = sample(preset, variant_seed)      # pure fn, budget-constrained
    build Tier-1 filtergraph(params)                 # pure fn
    [Tier 2 on?] insert neural stages
    render variant
    quality_guard(variant vs source)                 # VMAF + histogram sanity
        -> if below floor: reduce strength / regen (bounded retries)
    record params + exact cmd + metrics -> manifest
write manifest.json
```

`sample`, `build_filtergraph` are pure and unit-tested. Tier 2 ops are extra stages in the same
pipeline. A `--quality {fast,hq}` flag toggles the neural layer.

---

## 2. Folder / file structure

```
variant-maker/
  pyproject.toml
  README.md
  variant_maker/
    cli.py            # entrypoint + args
    probe.py          # ffprobe (incl. color tags) + sha256
    presets.py        # subtle/medium/strong range tables + per-variant budget
    platforms.py      # reels/tiktok/shorts -> {w,h,fps}
    sampler.py        # seed -> budgeted params (pure, tested)
    color.py          # source color tags -> correct in/out range + tagging (Tier 1)
    filtergraph.py    # params -> -vf / -af (pure, tested)
    quality.py        # VMAF + histogram/saturation sanity guard
    ffmpeg.py         # subprocess runner + cmd builder
    neural/           # Tier 2 (lazy-imported; absent install => Tier 1 still works)
      upscale.py      # Real-ESRGAN downscale->upscale
      interpolate.py  # RIFE/FILM retime
      protect.py      # segment + mask subject/face/text
    pipeline.py       # stage list: ffmpeg + neural stages in order
    manifest.py       # schema + writer
  tests/
    test_sampler.py            # same seed -> same params
    test_filtergraph.py
    test_color.py              # round-trips preserve saturation
    test_reproducibility.py
  scratch/            # frame round-trips for neural ops (gitignored)
  output/
```

---

## 3. CLI

```
variant-maker input.mp4 --count 10 --preset medium --platform reels --quality fast
```

| Flag | Default | Notes |
|---|---|---|
| `input` | — | source |
| `-n, --count` | 5 | variants |
| `--preset` | medium | subtle \| medium \| strong |
| `--platform` | none | reels \| tiktok \| shorts \| none |
| `--quality` | fast | `fast` = Tier 1 only (CPU) · `hq` = Tier 2 neural on (GPU) |
| `--seed` | random | master seed; per-variant derived |
| `-o, --out` | ./output | |
| `--quality-floor` | vmaf 90 | reject+regen below this |
| `--max-regen` | 3 | bounded retries before accepting best-effort |
| `--rotate` | never | never \| safe |
| `--flip` | never | hflip mirrors text/logos |
| `--jobs` | 1 | parallel (Tier 1); serialize GPU stages |
| `--dry-run` / `-v` | off | print cmds / verbose |

---

## 4. Tier 1 — FFmpeg core

### 4a. Color correctness (the actual wash-out fix — do this first, it's free)

The "under-saturated, flat, looks horrible" symptom is almost always a **color tagging /
range-handling bug**, not missing AI. Re-encoding while dropping or mismatching color metadata
(full/`pc` vs limited/`tv` range; `bt709` primaries/transfer/matrix for HD) makes players
misinterpret the pixels → desaturated, washed out. Fix it here and most ugliness disappears before a
model ever runs.

Rules:
1. **Probe the source color tags** (`ffprobe -show_streams`: `color_range`, `color_space`,
   `color_primaries`, `color_transfer`). Don't assume.
2. **Convert with range-aware filters.** Use `zscale` (or `colorspace`) for any colorspace/range
   change — never let a naive `scale` reinterpret range. If staying in bt709, still set
   `format=yuv420p` at the correct point and avoid filters that silently flip range.
3. **Tag the output explicitly** so players don't guess:
   `-colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv` (HD defaults; carry
   source values when they differ).
4. **Color shifts must be zero-mean.** Sample brightness/contrast/saturation symmetrically around
   neutral — sometimes up, sometimes down. Never apply a systematic desaturation; that's exactly the
   pre-Smart-Repurpose look.

A `test_color.py` round-trip (encode→decode, compare mean saturation to source) should stay within a
tight tolerance. If it doesn't, the color path is broken — fix before anything else.

### 4b. Perceptual budget (stop transforms from compounding into mush)

Give each variant a total distortion **budget** and distribute it across axes, so you never land
max-desat + heavy-grain + high-CRF on the same output. Sample axes, then scale them down to fit the
budget. This is what keeps `strong` from looking like a `strong` *degradation*.

### 4c. Filtergraph order

```
trim -> crop -> zscale/scale(platform, range-aware) -> [rotate w/ fill+crop] ->
eq(color) -> hue -> unsharp -> grain -> fps -> setpts(tempo) -> format=yuv420p -> tag color
```
Audio mirrors time changes: `atrim` identical to video, one `speed` factor → `atempo`, optional
`equalizer`, `loudnorm`, aac re-encode + strip meta. (Pitch only via `rubberband`; else drop it — a
naive `asetrate` desyncs.)

### 4d. Quality guard (in-loop, CPU)

Two checks, run on every variant; fail → reduce strength and regenerate (bounded by `--max-regen`):

- **Histogram / saturation sanity (always on, cheap):** compare output luma + saturation histograms
  to source. Directly catches wash-out, crushed blacks, blown highlights. ~free.
- **VMAF (stronger, optional):** `libvmaf`, CPU. **Frame-alignment caveat:** VMAF needs reference and
  distorted at the **same resolution and frame count**, aligned — so you can't VMAF across trim /
  tempo / fps changes. Solution: compute VMAF on a **quality render** = source with only the
  *quality-affecting* ops (color, sharpen, grain, scale, encode) at source geometry/timing (no
  trim/tempo/fps). The shipped variant additionally applies the temporal/geometric identity ops,
  which don't materially change perceptual quality. Floor default VMAF ≥ 90.

### 4e. Parameter ranges (subtle / medium / strong)

| Video param | subtle | medium | strong |
|---|---|---|---|
| crop punch-in (kept, rescaled) | 0.98–1.00 | 0.92–0.96 | 0.88–0.93 |
| rotation deg (`safe` only) | 0 | ±0.3 | ±0.8 |
| brightness (zero-mean) | ±0.01 | ±0.025 | ±0.04 |
| contrast | 0.99–1.01 | 0.97–1.03 | 0.95–1.06 |
| saturation (zero-mean) | 0.99–1.02 | 0.96–1.05 | 0.92–1.10 |
| gamma | 0.99–1.01 | 0.97–1.03 | 0.95–1.05 |
| hue deg | ±1 | ±3 | ±6 |
| grain (see Tier 2 note) | 3–6 | 7–12 | 10–16 |
| unsharp | off | ~0.3 | ~0.4 |
| speed `s` | 0.99–1.01 | 0.98–1.02 | 0.96–1.04 |
| trim/end (s) | 0–0.10 | 0.10–0.30 | 0.20–0.50 |
| CRF | 18–20 | 19–22 | 20–23 |
| GOP | 48/60 | 48/60/90 | 60/90/120 |
| Social maxrate (reels/tiktok/shorts) | 12M ceiling (constrained VBR; `none` uncapped) | same | same |

| Audio param | subtle | medium | strong |
|---|---|---|---|
| loudnorm I (LUFS) | -14 | -15…-13 | -16…-13 |
| EQ | 1 band ±1dB | 1–2 bands ±2dB | 2 bands ±3dB |
| speed | = video `s` | = video `s` | = video `s` |
| pitch (rubberband only) | none | 0…±2% | ±2…±4% |
| aac bitrate | 160k | 128–192k | 128–192k |

(Ranges are then clamped by the per-variant budget in 4b.)

---

## 5. Tier 2 — Neural layer (the "Smart Repurpose" quality leap)

Principle: **reconstructive ops that invent plausible detail**, not destructive ops that degrade.
Each plugs in at a defined point and is gated by the same quality guard.

| Op | Model (practical pick) | Where it plugs in | Why it's the leap |
|---|---|---|---|
| **Downscale → neural upscale** (hero op) | Real-ESRGAN (`realesrgan-ncnn-vulkan` for broad GPU support; PyTorch for control) | replaces the `scale` step: drop to 540/720p, AI-upscale to target | invents clean, plausible detail → output is sharp *and* statistically distinct (new pixels). Looks **better**, not worse. |
| **Neural denoise / regrade** | Real-ESRGAN denoise variant, or a learned regrade | replaces additive `grain` | additive `noise` is exactly what makes naive output look cheap; this adds variation without the cheapness |
| **AI frame interpolation** | RIFE (`rife-ncnn-vulkan` / Practical-RIFE); FILM for higher quality | replaces tempo/fps resample | synthesizes real in-between frames for any speed/fps change instead of janky drop/dupe |
| **Content-aware protection** | SAM or MediaPipe (subject/face) + a text detector (EAST/PaddleOCR) | mask computed once, gates where destructive transforms apply | shields faces/text/subject from crop + upscale artifacts — the "don't wreck the important part" guarantee |
| **Auto-tune to minimum** | controller (bisection on quality vs difference) | wraps the pipeline | finds the minimum transform that hits the difference target while staying above the quality floor |

Recommended default install: **ncnn-vulkan** builds (Real-ESRGAN + RIFE) — run on a wide range of
GPUs without a full PyTorch stack, take image sequences, easy to ship. Upgrade to PyTorch when you
need finer control.

### Neural pipeline integration

Neural ops are frame-based, so the pipeline round-trips through frames:

```
ffmpeg: decode + trim + color-correct  -> lossless frames (scratch/)
[optional] downscale frames
Real-ESRGAN upscale frames
[optional] RIFE interpolate/retime frames
ffmpeg: frames -> apply remaining color/encode + audio + tag color -> final variant
quality_guard
```

Use a **lossless intermediate** (PNG or FFV1) for the frame round-trip so you don't double-compress.
Round-trips cost disk + time — that's the GPU-tier tradeoff, and it's justified now that
indistinguishable quality is the explicit objective.

---

## 6. Manifest schema (v0.2)

```json
{
  "tool": "variant-maker",
  "version": "0.2.0",
  "created_utc": "2026-06-27T18:30:00Z",
  "source": {
    "path": "input.mp4", "sha256": "…",
    "duration_s": 34.2, "width": 1080, "height": 1920, "fps": 30, "has_audio": true,
    "color": { "range": "tv", "primaries": "bt709", "transfer": "bt709", "matrix": "bt709" }
  },
  "run": {
    "master_seed": 1234567890, "preset": "medium", "platform": "reels",
    "quality_mode": "hq", "count": 10, "quality_floor": { "metric": "vmaf", "value": 90 },
    "ffmpeg_version": "6.1.1"
  },
  "variants": [
    {
      "index": 1, "filename": "input_v01_8a3f1c2d.mp4", "seed": 987654321,
      "output_sha256": "…", "duration_s": 33.9,
      "tier": 2,
      "neural_ops": [
        { "op": "upscale", "model": "RealESRGAN-x4plus", "version": "0.2.5", "from": "720p", "to": "1080p" },
        { "op": "interpolate", "model": "rife-v4.6" }
      ],
      "params": { "video": { "...": "..." }, "audio": { "...": "..." } },
      "quality": { "vmaf": 94.1, "histogram_ok": true, "regen_count": 0, "passed": true },
      "ffmpeg_cmd": "ffmpeg … ",
      "platform_result": null
    }
  ]
}
```

`platform_result` is the bridge to any future detector: test a batch, drop in `"pass"`/`"fail"`, and
you've got labeled `recipe -> outcome` data for free. Keeping that field honest from day one is the
only thing the later detector needs from this project.

---

## 7. Build order

**Tier 1 first — ship this before touching the GPU:**
1. `probe.py` — meta **including color tags** + sha256.
2. `color.py` — correct range/tagging + the `test_color.py` saturation round-trip. *(This is the
   wash-out fix; validate it before building anything on top.)*
3. `sampler.py` — seed → budgeted params (pure).
4. `filtergraph.py` — params → `-vf`/`-af` (pure); `--dry-run` prints.
5. `ffmpeg.py` — render one variant end-to-end; confirm color is correct and audio in sync.
6. `quality.py` — histogram sanity guard (always on), then VMAF quality-render guard.
7. `manifest.py` + `cli.py` + presets + platforms. **Ship Tier 1.**

**Tier 2 — add one op at a time, biggest lever first:**
8. `neural/upscale.py` (Real-ESRGAN) — the hero quality op. Most of the visible gain is here.
9. `neural/interpolate.py` (RIFE) — for clean retiming.
10. `neural/protect.py` — segment + protect faces/text.
11. Auto-tune-to-minimum controller.

Each step independently testable. Tier 2 lazy-imports, so a machine without the models still runs
Tier 1.

---

## 8. Gotchas

- **Color tagging end-to-end** — the #1 wash-out cause. Probe source tags, convert range-aware
  (`zscale`), tag output explicitly. Verify with the saturation round-trip test.
- **Zero-mean shifts** — never systematically desaturate/darken; that *is* the cheap look.
- **VMAF frame alignment** — can't compute across trim/tempo/fps changes. Use the quality-render
  (quality ops only, source geometry/timing). Histogram guard covers what VMAF can't.
- **Even dimensions** — libx264 needs even w/h: `scale=trunc(iw/2)*2:trunc(ih/2)*2`. Most common
  cross-clip breakage.
- **Audio sync** — one `speed` factor on both streams; identical trims; pitch via `rubberband` or not
  at all.
- **Per-frame neural upscale flicker** — frame-independent upscaling can shimmer temporally on video.
  Mitigate with a temporally-stable model/setting or mild output denoise; budget for it.
- **Real-ESRGAN over-smoothing** — can plasticize skin / over-sharpen. Pick the right model variant,
  tune denoise strength, and protect faces (Tier 2 op 3).
- **Lossless intermediate for frame round-trips** — PNG/FFV1, or you double-compress and lose the
  quality you paid GPU for.
- **Reproducibility** — same seed → identical *params* (pure sampling), guaranteed. Identical *bytes*
  are **not** guaranteed (x264 nondeterminism; neural ops add more). Pin versions; treat the manifest
  `ffmpeg_cmd` + recorded params as the reproduction contract, not byte-equality.
- **Metadata** — `-map_metadata -1` + `-fflags +bitexact`; watch phone-source rotation display-matrix
  side data (can flip output).
