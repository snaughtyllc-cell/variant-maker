"""STUB — Phase 3. Seed -> budgeted params. PURE & deterministic (unit-tested).

Contract:
  derive_seed(master, index) -> stable per-variant seed
  sample(preset, seed) -> Params dict {"video": {...}, "audio": {...}}
    - every axis drawn from preset ranges via a seeded RNG
    - color axes are zero-mean (straddle neutral)
    - axes scaled down so total normalized distortion <= preset.budget
    - audio.speed MUST equal video.speed (sync); pitch only if rubberband available
"""
from __future__ import annotations

import hashlib

from .presets import Preset


def derive_seed(master_seed: int, index: int) -> int:
    """Deterministic per-variant seed. Implemented (trivial, lets Phase 3 tests anchor)."""
    h = hashlib.sha256(f"{master_seed}:{index}".encode()).digest()
    return int.from_bytes(h[:8], "big")


def sample(preset: Preset, seed: int, *, rubberband: bool = False) -> dict:
    raise NotImplementedError("Phase 3: draw budgeted, zero-mean params from preset ranges")
