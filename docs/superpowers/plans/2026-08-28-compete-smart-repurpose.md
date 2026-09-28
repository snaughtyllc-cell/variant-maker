# Compete smart-repurpose axes — implementation plan

> TDD. Spec: `docs/superpowers/specs/2026-08-28-compete-smart-repurpose.md`.
> Separate RNG for new sample axes. Do not pin live Fast.

```
./.venv/bin/pytest tests/test_sampler.py tests/test_filtergraph.py tests/test_ffmpeg.py tests/test_quality.py tests/test_pipeline.py -q -m "not integration"
```

## Task 1 — Sampler + rotate safe

- `vignette` + `out_fps` via `Random(int(seed) ^ 0xF95)` after the main draw.
- `FPS_CHOICES = (30, 48, 60)`.
- `apply_rotate_safe(deg, shot)`: talking_head clamp **0.35–0.8**; else **0.7–1.3**. Sign preserved. Exact 0 on a zero-width preset stays 0.
- Pipeline default `rotate=safe`. `never` still zeros.

## Task 2 — Filtergraph + quality

- `vignette=` after color when amount > 0.
- `fps=` from `out_fps` else platform fps.
- `_QUALITY_NEUTRAL` zeros vignette, out_fps, rotate.

## Task 3 — Optional US metadata

- `ffmpeg.us_metadata_args(seed)` pure.
- `build_render_cmd` appends them when `params["us_metadata"]`.
- Still `-map_metadata -1`. Off unless `--us-metadata`.
