# PLAN.md — variant-maker build

Phased, test-driven. Execute in order. **Stop at each checkpoint for review** before the next
phase. Each phase: write the failing test first, implement to green, then refactor.

Status legend: ✅ done & verified · 🔨 to build

---

## Phase 0 — Harness  ✅
- Project scaffold, `pip install -e ".[dev]"`, `pytest` runs, ffmpeg detected.
- **Acceptance:** `pytest -q` is green (10 passed, 2 xfailed). ✅ verified.

## Phase 1 — Probe  ✅
- `probe.py`: ffprobe → SourceInfo incl. color tags; sha256.
- **Acceptance:** `test_probe.py` green (geometry, audio flag, color tags, unknown→None). ✅

## Phase 2 — Color correctness  ✅  ← the wash-out fix, do not regress
- `color.py`: resolve/carry tags, range-aware conversion, even scaling, explicit output tags.
- **Acceptance:** `test_color.py` green INCLUDING the ffmpeg saturation round-trip
  (`test_saturation_roundtrip_preserved`) — output saturation within 8% of source. ✅ verified.
- Everything below must keep this test green.

## Phase 3 — Sampler  🔨  ← START HERE
- Implement `sampler.sample(preset, seed, *, rubberband=False) -> {"video":..,"audio":..}`.
- Rules: draw each axis from preset ranges via seeded RNG; color axes zero-mean; scale axes
  to fit `preset.budget`; `audio.speed == video.speed`; pitch only if `rubberband`.
- **Tests:** flip the two xfails in `test_sampler.py` to real asserts; add budget + zero-mean
  (mean over many seeds ≈ neutral) + range-bounds tests.
- **Checkpoint:** review sampling distribution before wiring filters.

## Phase 4 — Filtergraph  🔨
- Implement `filtergraph.build_video_filters` / `build_audio_filters` (PURE).
- Enforce documented order; use `color.even_scale_filter` / `zscale_convert_filter` for scale.
- **Tests:** golden-string tests for representative params; assert no naive `scale` reinterprets
  range; assert audio `atempo` matches video speed.
- **Checkpoint:** review a few generated filtergraphs by eye.

## Phase 5 — Render one variant  🔨
- Implement `ffmpeg.render_variant`: full cmd with `output_color_args`, `-map_metadata -1`,
  `-fflags +bitexact`, libx264 crf/gop, aac. Return (path, cmd_str).
- **Acceptance (integration):** render one real variant; assert it plays, audio in sync,
  color preserved (reuse the saturation check), dimensions even.
- **Checkpoint:** eyeball one output. Does it look like a real video?

## Phase 6 — Quality guard  🔨
- `quality.histogram_sanity` (always on) + `quality.vmaf` (on the geometry/time-matched
  QUALITY RENDER — cannot vmaf across trim/tempo/fps).
- Wire reject→reduce-strength→regen, bounded by `--max-regen`.
- **Tests:** a deliberately ugly variant fails the guard; a clean one passes.
- **Checkpoint:** confirm guard catches a forced wash-out.

## Phase 7 — Pipeline + CLI → SHIP TIER 1  🔨
- `pipeline.run`: probe → per-variant (sample→filtergraph→render→guard→record) → manifest.
- Wire naming, `--out`, `--dry-run`, `--jobs`.
- **Acceptance:** `variant-maker clip.mp4 -n 5 --preset medium --platform reels` produces 5
  good variants + a valid `manifest.json` with `platform_result: null` per variant.
- **🚢 Tier 1 ships here.** Tag it. Everything below is upside.

## Phase 8 — Neural upscale (hero op)  🔨
- `neural/upscale.py`: downscale → Real-ESRGAN upscale over a lossless frame round-trip.
- Gate behind `--quality hq`; lazy-import. Mitigate temporal flicker.
- **Acceptance:** hq variant beats fast variant on VMAF/sharpness while staying distinct.

## Phase 9 — Neural interpolation  🔨
- `neural/interpolate.py`: RIFE retime for speed/fps changes (replaces drop/dupe).

## Phase 10 — Content protection  🔨
- `neural/protect.py`: segment subject/face/text; mask gates destructive transforms.

## Phase 11 — Auto-tune controller  🔨
- Bisection on transform strength → minimum that hits the difference target above the
  quality floor.

---

### Definition of done (every phase)
Tests written first and green · `ruff` clean · invariants in CLAUDE.md upheld · for render
phases, a real output eyeballed · `pytest` output shown before claiming done.
