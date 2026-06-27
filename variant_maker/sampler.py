"""Phase 3. Seed -> budgeted params. PURE & deterministic (unit-tested).

Contract:
  derive_seed(master, index) -> stable per-variant seed
  sample(preset, seed, *, rubberband=False) -> Params {"video": {...}, "audio": {...}}
    - every axis drawn from preset ranges via a seeded RNG
    - color/geometry axes are ZERO-MEAN (straddle neutral) — no systematic shift
    - transform axes scaled down so total normalized distortion <= preset.budget
    - audio.speed MUST equal video.speed (sync); pitch only if rubberband available
  total_distortion(preset, params) -> the normalized distortion these params spend

The distortion model is the budget contract: each budgeted axis contributes a value in
[0, 1] measuring how far it strays from its calm point, relative to its in-range reach.
sample() shrinks every budgeted axis toward its calm point by one shared factor when the
raw draw overspends, which keeps zero-mean symmetry and the [lo, hi] bounds intact.
"""
from __future__ import annotations

import hashlib
import random

from .presets import Preset

# Axis model. kind "sym" => zero-mean around `ref` (a neutral value); kind "dir" => one-
# directional, calm at the range end named by `ref` ("lo" or "hi"). `budgeted` axes share
# the per-variant distortion budget; temporal axes (speed, trim) ride along unbudgeted.
_SYM, _DIR = "sym", "dir"
_VIDEO_AXES = (
    # (name,        kind,  ref,    budgeted)
    ("crop_keep",   _DIR,  "hi",   True),
    ("rotate_deg",  _SYM,  0.0,    True),
    ("brightness",  _SYM,  0.0,    True),
    ("contrast",    _SYM,  1.0,    True),
    ("saturation",  _SYM,  1.0,    True),
    ("gamma",       _SYM,  1.0,    True),
    ("hue_deg",     _SYM,  0.0,    True),
    ("grain",       _DIR,  "lo",   True),
    ("unsharp",     _DIR,  "lo",   True),
    ("crf",         _DIR,  "lo",   True),   # encoder degradation counts toward the budget
    ("speed",       _SYM,  1.0,    False),  # temporal identity ops ride along unbudgeted
    ("trim_s",      _DIR,  "lo",   False),
)
# crf is output as an int (floored toward its calm 'lo' end, so its budget share never grows).
_INT_AXES = frozenset({"crf"})


def derive_seed(master_seed: int, index: int) -> int:
    """Deterministic per-variant seed."""
    h = hashlib.sha256(f"{master_seed}:{index}".encode()).digest()
    return int.from_bytes(h[:8], "big")


def _calm_point(kind, ref, lo: float, hi: float) -> float:
    """The least-distorting value of an axis within its range."""
    if kind == _SYM:
        return ref
    return hi if ref == "hi" else lo


def _reach(kind, ref, lo: float, hi: float) -> float:
    """Normalizing span: tightest symmetric half-width (sym) or full width (dir)."""
    if kind == _SYM:
        return min(ref - lo, hi - ref)
    return hi - lo


def _axis_distortion(kind, ref, lo: float, hi: float, value: float) -> float:
    reach = _reach(kind, ref, lo, hi)
    if reach <= 0:
        return 0.0
    return abs(value - _calm_point(kind, ref, lo, hi)) / reach


def total_distortion(preset: Preset, params: dict) -> float:
    """Sum of normalized distortion across budgeted axes (the budget metric)."""
    v = params["video"]
    total = 0.0
    for name, kind, ref, budgeted in _VIDEO_AXES:
        if not budgeted:
            continue
        r = getattr(preset, name)
        total += _axis_distortion(kind, ref, r.lo, r.hi, v[name])
    return total


def sample(preset: Preset, seed: int, *, rubberband: bool = False, strength: float = 1.0) -> dict:
    """Draw budgeted, zero-mean params for one variant.

    `strength` in [0, 1] is the lever the auto-tune controller / quality guard drives: it
    caps total distortion at `strength * preset.budget`. 1.0 spends the full budget; lower
    values yield gentler variants. The seed fixes WHICH axes move; strength fixes how far.
    """
    strength = min(1.0, max(0.0, strength))
    budget = preset.budget * strength
    rng = random.Random(seed)

    # Draw every continuous axis in a fixed order (order anchors reproducibility).
    raw: dict[str, float] = {}
    for name, kind, ref, _budgeted in _VIDEO_AXES:
        r = getattr(preset, name)
        if kind == _SYM:
            d = min(ref - r.lo, r.hi - ref)
            raw[name] = ref + rng.uniform(-d, d)
        else:
            raw[name] = rng.uniform(r.lo, r.hi)

    # Fit the budget: shrink every budgeted axis toward its calm point by one factor.
    spent = sum(
        _axis_distortion(kind, ref, getattr(preset, name).lo, getattr(preset, name).hi, raw[name])
        for name, kind, ref, b in _VIDEO_AXES if b
    )
    if spent > budget and spent > 0:
        factor = budget / spent
        for name, kind, ref, b in _VIDEO_AXES:
            if not b:
                continue
            r = getattr(preset, name)
            calm = _calm_point(kind, ref, r.lo, r.hi)
            raw[name] = calm + factor * (raw[name] - calm)

    gop = rng.choice(preset.gop_choices)

    video = dict(raw)
    # Floor int axes toward their calm 'lo' end so the rounded value never exceeds its
    # budgeted share (keeps total_distortion(params) <= budget a hard guarantee).
    for name in _INT_AXES:
        video[name] = int(video[name])
    video["gop"] = gop

    # Audio mirrors the single speed factor; everything else drawn independently.
    eq_d = min(0.0 - preset.eq_gain_db.lo, preset.eq_gain_db.hi - 0.0)
    eq_gains = [rng.uniform(-eq_d, eq_d) for _ in range(preset.eq_bands)]
    loudnorm_i = rng.uniform(preset.loudnorm_i.lo, preset.loudnorm_i.hi)
    aac_kbps = int(round(rng.uniform(preset.aac_kbps.lo, preset.aac_kbps.hi)))
    if rubberband:
        p_d = min(0.0 - preset.pitch_pct.lo, preset.pitch_pct.hi - 0.0)
        pitch_pct = rng.uniform(-p_d, p_d)
    else:
        pitch_pct = 0.0

    audio = {
        "speed": video["speed"],  # invariant 3: one speed factor on both streams
        "loudnorm_i": loudnorm_i,
        "eq_bands": preset.eq_bands,
        "eq_gains": eq_gains,
        "pitch_pct": pitch_pct,
        "aac_kbps": aac_kbps,
    }

    return {"video": video, "audio": audio}
