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
  Crop punch can keyframe start→end (`crop_*_end_frac`) plus two-sine handheld wander;
  missing/equal ends stay the static crop golden. ✅ 45 passed, ruff clean.

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
  (ThreadPool); `--rotate` defaults to **safe** (TikFusion-class bands); `never` still zeroes;
  `--us-metadata` is off unless asked; ffmpeg version pinned in the manifest.
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
- **Throughput (do not skip):** HQ is serial today (`jobs: 1` on the worker). CUDA Real-ESRGAN
  defaults to **half precision** (no `--fp32`; set `VARIANT_MAKER_ESRGAN_FP32=1` to restore).
  20 HQ variants still queue one-after-another and can hit the RunPod **20 min** cap unless
  the endpoint execution timeout is raised (docs: 3600s for HQ experiments). Usual ~20 stays **Fast**.

## Phase 9 — Neural interpolation  ✅
- `neural/interpolate.py`: gated module (`available` / `needed` / `build_interpolate_cmd` +
  `interpolate_dir`) and HQ hook in `upscale_clip` (`defer_tempo` on neural-pre, RIFE after PNG
  extract). Fast is unchanged (never calls `upscale_clip`). No RIFE binary in Docker yet.

## Phase 10 — Content protection  ✅
- `neural/protect.py`: mid-frame grab + face boxes (MediaPipe if present, else OpenCV Haar).
  `apply_to_params` after `sample()` on **HQ only**. Fast skips face-protect: talking-head
  Haar coverage ≥15% used to set `crop_keep=1.0` and land ~22 bits / all-esc. No SAM.
  No face → identity. On HQ, face near an edge raises `crop_keep`; large coverage disables crop.

## Phase 11 — Auto-tune controller  ✅
- Bisection on `sample(..., strength=…)` → uniqueness (SSIM bits/64, default
  `uniqueness.DEFAULT_TARGET` = 24/64). **Fast default on** (`stop_on_clear` so a pack
  stops at the first uniqueness+quality+peer hit). HQ stays **off** (one Real-ESRGAN pass).
  Opt out with `auto_tune=False` / `--no-auto-tune`. Path-B 35% similarity is later.
- Fast *gate* is **24 bits vs source**, **24 vs peers** (~38% UI). Do not raise the gate
  to 32. Medium crop is unbudgeted `0.92–0.96` (caption-safe; 0.84 + edge
  window cropped a word). Warp is budgeted again so VMAF can cap it. Grain is
  uniqueness texture (7–12 / 10–16); social delivery is capped at 12M. Peer miss searches **stronger** (not milder — quality
  `passed` is VMAF only). Over-budget `sample()` shrinks color/encode first; crop_keep
  is fingerprint and does not shrink toward identity. Color stays zero-mean. VMAF floor stays.
  Gallery uniqueness % (higher = more different) plus an `esc` badge when escalated.
- Note: low similarity + high quality typically requires Tier 2 (neural) ops, not Tier 1 alone.

## Phase 12 — Platform outcome tracking (learning loop)  ⏸ skipped for now
- Spec still exists (`docs/superpowers/specs/2026-08-18-platform-outcome-learning.md`).
- **Do not build this next.** Gallery labeling / Drop Ledger learning / `platform_result`
  bias is deferred until we ask for it. Unlabeled stays pass; the field remains on the manifest.
- After Fast is the daily pack, next *product* work is Fast look/uniqueness — not Phase 12.

## Phase 14 — Split pack across creator destinations  ✅
- One generate → partition variants into **main / trial / growth** Drive folders
  (one Repurpose queue each). Same niche caption folder; different files per account.
- Spec: `docs/superpowers/specs/2026-08-19-creator-pack-split.md`.
- Studio Send to Drive: **Split pack** with three choosable destination dropdowns.
  Any subset can be filled (Growth empty is a 2-way split; one dest can take all).
  File counts must **sum to the selected total**. Default 20×3 is 1–7 / 8–14 / 15–20.
  `POST /api/drive/exports/split` starts one existing export job per destination.
  No re-render. Do **not** point three workflows at the same inbox.

## Phase 15 — Fast parallel / slim CPU worker  ✅ shipped (scale to zero)
- Fast is CPU x264; HQ is GPU. Pipeline already parallelizes Fast (`jobs` + uniqueness lock).
  Spec: `docs/superpowers/specs/2026-08-19-fast-worker-split.md`.
- **Shipped:** Fast `jobs` up to 8 in the payload (`encode_jobs_for_worker`). Worker must
  **not** recap to `os.cpu_count()` (GPU serverless often reports 1 — that serialized
  the Norway-wood 20-pack). HQ stays 1.
- **Shipped:** `count <= 3` Fast on Studio CPU when no Fast endpoint is set
  (`VARIANT_FAST_LOCAL_MAX`). Do **not** send 20-packs to Railway.
- **Now:** slim Fast CPU image (`deploy/runpod/Dockerfile.fast` →
  `ghcr.io/snaughtyllc-cell/variant-fast:latest`). All Fast goes to
  `RUNPOD_FAST_ENDPOINT_ID` when set (min workers 0). HQ stays on the 4090
  (`RUNPOD_ENDPOINT_ID`). Overnight both scale to $0.
- **Do not:** split one 20-pack across CPU+GPU. **Do not:** always-on workers.

## Phase 13 — Stronger audio uniqueness  ✅
- Video variants already re-encode audio (speed=`atempo` locked to video, EQ, loudnorm, AAC).
  Pitch is **on** when ffmpeg lists the `rubberband` filter (`has_rubberband()`, cached);
  omitted when the filter is absent so encodes never fail. One speed still: `atempo` =
  video speed; pitch is rubberband only (never a second speed factor / asynchs).
- Fast path: `pipeline.run` auto-detects after reading `jobs` and sets `config["rubberband"]`.
  Preset ranges remain tiny (±2% medium, ±4% strong).

## Phase 16 — Fast seeded resample + look (color + pixel seed)  ✅
- Spec: `docs/superpowers/specs/2026-08-19-fast-seeded-resample.md`.
- Fast analog of TikFusion Random Pixels **without** weird output size. ±8–32 px
  was invisible at the 576×1024 uniqueness frame (talking-head 25–33%).
- **Now:** reconstructive `rebuild_scale` (medium 0.67–0.80 → ~720–864 then back
  to 1080×1920; strong 0.50–0.66 so escalate is a heavier rebuild). Spec:
  `docs/superpowers/specs/2026-08-21-fast-rebuild-scale.md`.
- Per-copy color **shows** (still zero-mean). Over-budget shrink kills grain/unsharp/crf
  first so crop AND eq survive. `warp_k1` is **budgeted** (VMAF-capped); unbudgeted
  warp scored VMAF 53–80 and dropped Drive uploads. HQ skips rebuild+warp (ESRGAN owns pixels).
- Unbudgeted rebuild fingerprint. Color zero-mean. VMAF floor stays. Gates stay 24/24.
- Look-first shot probe (`docs/superpowers/specs/2026-08-21-fast-shot-probe.md`):
  source 25% vs 75% self-bits < 24 → talking-head keeps a sharp rebuild and
  remaps uniqueness grain (576 sees grain, not mush); motion stays gentler.
  Not OpenCV. Not a detector.

## Studio UX — current-run only (note, not blocking 9–11)
- Studio’s right rail tracks **one job**. Clicking Generate is disabled until **New run**
  (keeps the last pack on the rail). **Cancel** stops a live job (RunPod `/cancel` + skip
  remaining variants). Default Fast count is **20**.
- **Batch** = drop several files, one Generate: one job, several source cards at once,
  they render in order on the same rail.

---

### Definition of done (every phase)
Tests written first and green · `ruff` clean · invariants in CLAUDE.md upheld · for render
phases, a real output eyeballed · `pytest` output shown before claiming done.
