# CLAUDE.md — variant-maker

Operating context for Claude Code. Read this first, every session.

## What this is
A local-first, CLI-first **video variant generator**. One source video in → N rendered
variants + a manifest out. The variants must read as **real, original videos** — not
degraded re-encodes. This tool IS the deliverable.

Full design: `docs/spec.md`. Build steps: `PLAN.md`.

## Scope guards (do not drift)
- **NOT a detector.** A local "would-the-platform-catch-this" predictor is a *later* project.
  For now the real platform is the oracle; we test variants on it and label them. The only
  hook we keep is the manifest's `platform_result` field. Unlabeled after a drop = pass;
  flagged/duplicate-reject is the miss. Easier labeling + Drop Ledger learning is **Phase 12**
  (`docs/superpowers/specs/2026-08-18-platform-outcome-learning.md`) — **skipped for now**;
  do not build it next. Not a built-in IG checker.
- **NOT a platform-spoofing engine.** Beating a specific detector is layered on later.
- Don't add Redis/queues/cloud/desktop-app/account-proxy logic. Local CLI only.

## Architecture: two tiers
- **Tier 1 — FFmpeg core (CPU, ships first, runs anywhere).** Correct color, budgeted
  transforms, in-loop quality guard. This alone fixes the washed-out look.
- **Tier 2 — Neural layer (GPU, optional).** Reconstructive ops (Real-ESRGAN upscale, RIFE
  interpolation, content protection) that make variants look as good or better than source.
  Lazy-imported — Tier 1 must run on a machine with no GPU/models.

## Invariants (violating these is a bug, even if tests are green)
1. **Color correctness is non-negotiable and comes first.** Probe source color tags, convert
   range-aware (zscale, never naive scale), and ALWAYS tag the output. `test_color.py`'s
   saturation round-trip must stay green before anything is layered on top. This is the
   wash-out fix — `variant_maker/color.py` already implements + passes it.
2. **Color shifts are zero-mean.** Never systematically desaturate/darken; that IS the cheap look.
3. **Audio stays in sync.** One `speed` factor on both streams (`setpts=PTS/s` ↔ `atempo=s`);
   identical trims. Pitch only via `rubberband`, else omit.
4. **`sampler.sample` and `filtergraph.build_*` are PURE functions.** Same seed → same params.
   They must be unit-testable without ffmpeg.
5. **Even dimensions** on every scale (`trunc(iw/2)*2`) — libx264 requirement.
6. **Every variant gates through the quality guard.** Below floor → reduce strength & regen.
7. **The manifest is the reproduction contract** (exact cmd + params), not byte-equality.
   x264/neural ops are not bit-deterministic. Keep the `platform_result` slot.

## Workflow (matches the user's existing setup)
- **TDD.** Red → green → refactor. Write the failing test first, then implement.
- **Execute `PLAN.md` phase by phase.** Stop at each checkpoint for review before moving on.
- **Verify before claiming done.** Run `pytest` and show output; never assert success without it.

## Commands
```
pip install -e ".[dev]"        # setup
pytest -q                       # all tests (incl. ffmpeg integration if ffmpeg present)
pytest -q -m "not integration"  # fast unit-only
variant-maker --help            # CLI
variant-maker in.mp4 -n 10 --preset medium --platform reels --dry-run
ruff check .                    # lint
```

## File ownership
| Module | State | Owns |
|---|---|---|
| `probe.py` | ✅ done | ffprobe meta incl. color tags + sha256 |
| `color.py` | ✅ done | color correctness (the wash-out fix), even scaling |
| `presets.py` | ✅ done | subtle/medium/strong ranges + per-variant budget |
| `platforms.py` | ✅ done | reels/tiktok/shorts profiles |
| `manifest.py` | ✅ done | manifest schema + writer (+ platform_result bridge) |
| `sampler.py` | ✅ done | seed → budgeted, zero-mean params (pure); encode-first over-budget shrink |
| `filtergraph.py` | ✅ done | params → -vf/-af in the documented order (pure); Fast resample + warp |
| `ffmpeg.py` | ✅ done | build + run one render; tag color on output |
| `quality.py` | ✅ done | histogram sanity + VMAF quality-render guard |
| `pipeline.py` | ✅ done | per-variant loop, uniqueness + auto-tune → manifest |
| `autotune.py` | ✅ done | bisection; quality fail → milder; source/peer miss → stronger |
| `uniqueness.py` | ✅ done | SSIM bits; live gate **32 vs source, 24 vs peers** |
| `cli.py` | ✅ done | options + `pipeline.run` |
| `neural/*` | ✅ Phase 8-10 | Tier 2: upscale, interpolate, protect (HQ) |
| Fast resample | ✅ done | seeded even round-trip + `warp_k1`; HQ skipped |

## Environment notes
- ffmpeg must be built with **libvmaf** for the Phase-6 VMAF guard (`ffmpeg -filters | grep vmaf`).
- Tier 2 uses external binaries (realesrgan-ncnn-vulkan, rife-ncnn-vulkan), not pip packages.
