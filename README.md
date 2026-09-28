# varimo

**Many originals from one master.**

Local-first AI video variant generator. One source video → N variants that read as real,
original videos (not degraded re-encodes) → plus a manifest.

> `varimo` is the product name. The repo, the Python package (`variant_maker/`), and the
> CLI (`variant-maker`, `variant-farm`, `variant-server`) keep their existing names.
> Brand assets and usage rules live in [`brand/`](brand/README.md).
>
> **This GitHub is Lab** (`snaughtyllc-cell/variant-maker`). Testers / production
> Studio are **`snaughtyllc-cell/varimo-live`**. Copy files over; do not merge.
> See [`docs/ops/two-githubs.md`](docs/ops/two-githubs.md).

- **Tier 1 (FFmpeg, CPU):** correct color, budgeted transforms, in-loop quality guard.
- **Tier 2 (neural, GPU, optional):** Real-ESRGAN upscale, RIFE interpolation, content
  protection — the quality leap to "can't tell the difference."

See `docs/spec.md` for the full design, `PLAN.md` for the build, `CLAUDE.md` for working rules.

## Setup
```bash
pip install -e ".[dev]"
pytest -q          # ffmpeg required for the color integration test
```
ffmpeg must be built with **libvmaf** for the quality guard (Phase 6).
Tier 2 needs external binaries: `realesrgan-ncnn-vulkan`, `rife-ncnn-vulkan`.

## Usage
```bash
variant-maker input.mp4 --count 10 --preset medium --platform reels
variant-maker input.mp4 -n 5 --preset strong --quality hq      # Tier 2 neural
variant-maker input.mp4 -n 3 --dry-run                          # print plan, render nothing
```

## Status
Tier 1 scaffold complete and verified through Phase 2 (color). Build continues from Phase 3
(sampler) per `PLAN.md`.

## Layout
```
variant_maker/   core package (probe, color, presets, platforms, manifest done; rest staged)
  neural/        Tier 2 ops (lazy-imported)
tests/           pytest suite incl. a real ffmpeg saturation round-trip
docs/spec.md     full design spec
CLAUDE.md        operating rules for Claude Code
PLAN.md          phased TDD build plan
```
