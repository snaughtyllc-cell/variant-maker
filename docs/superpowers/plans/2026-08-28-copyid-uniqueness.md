# Phase 17 — Copy-detection uniqueness heads

**Spec:** `docs/superpowers/specs/2026-08-28-copyid-uniqueness.md`  
**Lab:** `docs/ops/copyid-lab.md`

TDD. Extra heads are lazy. Fast default stays `copyid=off`.

## Tasks

1. Pure math (`copyid/compare.py`, `fuse.py`) + unit tests — no ffmpeg.
2. Chromaprint parse/match + `fpcalc` skip-if-missing.
3. Visual protocol + FakeBackend + Chamfer score.
4. Wire `uniqueness.score_uniqueness(..., copyid=, extra_heads=)` — existing SSIM tests stay green.
5. Pipeline + CLI `--copyid off|record|gate`; persist `quality.heads`.
6. Lazy SSCD / DINOv2 backends (available() only unless lab).
7. `@pytest.mark.lab` smoke; lab runbook.

Do not raise `TARGET_BITS`. Original-bed Chromaprint is diagnostic only —
never fuse audio into `gate`. Do not put SSCD on the slim Fast image.
