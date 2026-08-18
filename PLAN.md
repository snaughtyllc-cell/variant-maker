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

## Phase 3 — Sampler  ✅
- `sampler.sample(preset, seed, *, rubberband=False, strength=1.0) -> {"video":..,"audio":..}`.
- Rules: draw each axis from preset ranges via seeded RNG; color axes zero-mean; scale axes
  to fit `strength * preset.budget`; `audio.speed == video.speed`; pitch only if `rubberband`.
- **CRF counts toward the budget** (sampled continuous, floored to int toward its calm `lo`
  end so the rounded value never exceeds its budgeted share). GOP is an unbudgeted pick.
- **`strength` is the auto-tune lever** (not pinned to the ceiling): the controller / quality
  guard drives it per variant. Seed fixes WHICH axes move; strength fixes HOW far.
- `total_distortion(preset, params)` is the public budget metric.
- **Tests:** xfails flipped + reproducibility, budget, zero-mean, range-bounds, audio-bounds,
  pitch/rubberband, strength-scaling, crf-in-budget. ✅ 34 passed, ruff clean.

> **North star (the "B" goal):** the auto-tune controller (Phase 11) drives `strength` so each
> variant hits a measurable **similarity target** vs source (the ~35% anchor) while staying above
> the VMAF/watchability floor. Similarity is computed in `quality.py` (Phase 6). Predicting a
> platform's actual verdict stays out of scope — recorded via the manifest `platform_result` slot.

## Phase 4 — Filtergraph  ✅
- `filtergraph.build_video_filters` / `build_audio_filters` — PURE, documented order.
- Trim from START (mirrors to audio without needing duration); resize via `even_scale_filter`
  (`zscale_convert_filter` only if output target differs from carried source); rotation skipped
  below 0.05° (no-op sliver guard); eq/atempo/loudnorm always, other axes omitted when no-op.
- **Tests:** golden -vf/-af, load-bearing order, even/safe scale (no naive range reinterpret),
  atempo==video speed, no-audio→"", none-platform geometry, no-op omission, pitch-only-rubberband.
  ✅ 45 passed, ruff clean.

## Phase 5 — Render one variant  🔨
- Implement `ffmpeg.render_variant`: full cmd with `output_color_args`, `-map_metadata -1`,
  `-fflags +bitexact`, libx264 crf/gop, aac. Return (path, cmd_str).
- **Acceptance (integration):** render one real variant; assert it plays, audio in sync,
  color preserved (reuse the saturation check), dimensions even.
- **Checkpoint:** eyeball one output. Does it look like a real video?

## Phase 6 — Quality guard  ✅
- `histogram_sanity` (always-on YAVG/SATAVG check) + `vmaf` (libvmaf on `quality_render` —
  quality ops at source geometry/timing so frames align) + `passes_guard` (combined decision,
  floor 90) + `regen_until_pass` (reject→reduce strength→regen, bounded by max_regen; PURE/injected).
- **Verified:** washed-out (`saturation=0.3`) fails histogram; degraded (crf51/grain40) VMAF 9.4
  vs clean 99.9; regen loop reduces strength until pass and is bounded. ✅ 60 passed, ruff clean.

> **Cross-model review constraints (Codex, 2026-06-27) — design Phase 6 around these:**
> - **Quality floor ≠ difference target.** VMAF/histogram measure *quality* (did the encode/
>   color/grain degrade it). They run on the QUALITY RENDER (quality ops only, source geometry/
>   timing) so they do NOT punish intended trim/crop/rotate/tempo difference. The *similarity/
>   difference* target (~35% anchor) is a SEPARATE measured metric that drives auto-tune (Phase 11).
> - **Pick the difference metric explicitly** (Phase 11): SSIM/LPIPS/pHash/CLIP/embedding all
>   disagree — choose one, calibrate our own threshold (not TikFusion's 35% verbatim).
> - **VMAF is one signal, not truth** (weak on short/social/high-motion); pair with histogram.
> - **Budget weights are heuristic guardrails, not calibrated similarity** — recalibrate against
>   the measured metric once the loop exists.
> - Pin ffmpeg version in the manifest (Phase 7). Seeded head/tail trim split (vs always-from-start)
>   is a later diversity enhancement.

## Phase 7 — Pipeline + CLI → SHIP TIER 1  ✅  🚢
- `pipeline.run(config) -> Manifest`: probe → per-variant (sample→render→quality-render→guard
  with regen loop→record) → manifest. Returns the Manifest (the clean callable the farm wraps).
- Naming `<stem>_vNN_<seed8>.mp4` (seed-derived, reproducible); `--out`, `--dry-run`, `--jobs`
  (ThreadPool); `--rotate never` zeroes rotation; ffmpeg version pinned in the manifest.
- **Acceptance MET:** `variant-maker real_src.mp4 -n 5 --preset medium --platform reels --seed 7`
  → 5 passing variants (vmaf 100) + valid `manifest.json`, `platform_result: null` each. ✅
- **🚢 Tier 1 shipped.** 64 passed, ruff clean. Everything below is upside.

## Phase 8 — Neural upscale (hero op)  ✅ (local M1 verified)
- `neural/upscale.py`: `upscale_clip` = downscaled Tier-1 render → Real-ESRGAN frame upscale →
  reassemble at target, re-muxing the already-correct audio. Gated behind `--quality hq`,
  lazy-imported, graceful fallback; records `tier:2` + `neural_ops`.
- **Real-ESRGAN desaturates (~9%, isolated by stage).** Fixed with a MEASURED saturation match
  in reassembly → hq sat 14%→1.7% off, guard passes with 0 regens. Edge energy +25% vs plain scale.
- **Tile-seam corruption fixed:** must upscale at the model's NATIVE scale (4 for x4plus); `-s 2`
  on a 4x model produced misaligned tiles that passed dims+histogram but were visually broken
  (only caught by eye). `upscale_clip` now derives scale from `NATIVE_SCALE`.
- **Flicker checked OK:** on a high-motion clip, neural YDIF (10.1) ≤ fast (10.6) — no added shimmer.
- **Still TODO:** the linux/GPU-container build for the cloud worker (see farm spec).
- **Acceptance:** hq is sharper + more distinct than fast while staying in the quality floor. ✅

## Phase 9 — Neural interpolation  🔨
- `neural/interpolate.py`: RIFE retime for speed/fps changes (replaces drop/dupe).

## Phase 10 — Content protection  🔨
- `neural/protect.py`: segment subject/face/text; mask gates destructive transforms.

## Phase 11 — Auto-tune controller  🔨  ← the "B" payoff
- Bisection on `sample(..., strength=…)` → the strength that hits the **similarity target**
  (difference target, ~35% anchor — our own metric, calibrated; not TikFusion's number) while
  staying above the quality floor. This is where the AI owns per-variant intensity, not the user.
- Note: low similarity + high quality typically requires Tier 2 (neural) ops, not Tier 1 alone.

---

### Definition of done (every phase)
Tests written first and green · `ruff` clean · invariants in CLAUDE.md upheld · for render
phases, a real output eyeballed · `pytest` output shown before claiming done.
