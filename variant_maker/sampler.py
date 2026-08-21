"""Phase 3. Seed -> budgeted params. PURE & deterministic (unit-tested).

Contract:
  derive_seed(master, index) -> stable per-variant seed
  sample(preset, seed, *, rubberband=False, duration_s=None) -> Params {"video": {...}, "audio": {...}}
    - every axis drawn from preset ranges via a seeded RNG
    - color/geometry axes are ZERO-MEAN (straddle neutral) — no systematic shift
    - transform axes scaled down so total normalized distortion <= preset.budget
    - audio.speed MUST equal video.speed (sync); pitch only if rubberband available
  total_distortion(preset, params) -> the normalized distortion these params spend

The distortion model is the budget contract: each budgeted axis contributes a value in
[0, 1] measuring how far it strays from its calm point, relative to its in-range reach.
When the raw draw overspends, sample() shrinks ENCODE axes (grain/unsharp/crf) toward
calm first so per-copy color can still show. crop_keep and rebuild_scale are unbudgeted
(VMAF already ignores both). warp_k1 is budgeted again so the quality loop can cap it —
unbudgeted warp on talking-head scored VMAF 53–80 and dropped Drive uploads.
Color stays zero-mean; bounds stay intact.
"""
from __future__ import annotations

import hashlib
import random

from .presets import Preset, Range
from .shot import grain_range_for_shot, rebuild_range_for_shot

# Keep at least this much of a short clip after head+tail trim (ffmpeg needs remaining > 0).
_MIN_REMAINING_S = 0.05
_REMAINING_FRACTION = 0.5
_REMAINING_CAP_S = 1.0

# Axis model. kind "sym" => zero-mean around `ref` (a neutral value); kind "dir" => one-
# directional, calm at the range end named by `ref` ("lo" or "hi"). `budgeted` axes share
# the per-variant distortion budget; temporal axes (speed, trim) ride along unbudgeted.
# crop_keep and rebuild_scale are unbudgeted: vs-source uniqueness levers. VMAF
# already ignores both (quality proxy is platform=none + identity rebuild).
# warp_k1 is budgeted so VMAF regen can shrink it; unbudgeted warp wrote
# best_effort files that harvest skipped.
_SYM, _DIR = "sym", "dir"
_VIDEO_AXES = (
    # (name,           kind,  ref,    budgeted)
    ("crop_keep",      _DIR,  "hi",   False),
    ("rebuild_scale",  _DIR,  "hi",   False),  # reconstructive round-trip; 1.0 = skip
    ("rotate_deg",     _SYM,  0.0,    True),
    ("brightness",     _SYM,  0.0,    True),
    ("contrast",       _SYM,  1.0,    True),
    ("saturation",     _SYM,  1.0,    True),
    ("gamma",          _SYM,  1.0,    True),
    ("hue_deg",        _SYM,  0.0,    True),
    ("grain",          _DIR,  "lo",   True),
    ("unsharp",        _DIR,  "lo",   True),
    ("crf",            _DIR,  "lo",   True),   # encoder degradation counts toward the budget
    ("warp_k1",        _SYM,  0.0,    True),   # VMAF-capped pixel seed
    ("speed",          _SYM,  1.0,    False),  # temporal identity ops ride along unbudgeted
    ("trim_s",         _DIR,  "lo",   False),
)
# crf is output as an int (floored toward its calm 'lo' end, so its budget share never grows).
_INT_AXES = frozenset({"crf"})
# Over-budget shrink: collapse cheap-look encode first so color still shows.
_ENCODE_AXES = frozenset({"grain", "unsharp", "crf"})
_LOOK_AXES = frozenset({
    "rotate_deg",
    "brightness", "contrast", "saturation", "gamma", "hue_deg",
    "warp_k1",
})
# Back-compat alias used by older tests/docs: encode + color (not geometry).
_COLOR_ENCODE_AXES = _ENCODE_AXES | frozenset({
    "brightness", "contrast", "saturation", "gamma", "hue_deg",
})
_GEOMETRY_AXES = frozenset({"crop_keep", "rotate_deg", "warp_k1", "rebuild_scale"})

# Unbudgeted Fast pixel seed: even px off target width, never 0, never a 2px peek.
# Mix of smaller and larger intermediates so we do not systematically soften one way.
RESAMPLE_PX_CHOICES = tuple(x for x in range(-32, 33, 2) if abs(x) >= 8)
RESAMPLE_FLAGS = ("lanczos", "spline", "bicubic")


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


def _spent_on(raw: dict[str, float], preset: Preset, names: frozenset[str]) -> float:
    total = 0.0
    for name, kind, ref, budgeted in _VIDEO_AXES:
        if not budgeted or name not in names:
            continue
        r = getattr(preset, name)
        total += _axis_distortion(kind, ref, r.lo, r.hi, raw[name])
    return total


def _shrink_toward_calm(
    raw: dict[str, float], preset: Preset, names: frozenset[str], factor: float,
) -> None:
    """Scale named axes toward their calm point. factor=0 collapses to calm; 1 keeps raw."""
    for name, kind, ref, budgeted in _VIDEO_AXES:
        if not budgeted or name not in names:
            continue
        r = getattr(preset, name)
        calm = _calm_point(kind, ref, r.lo, r.hi)
        raw[name] = calm + factor * (raw[name] - calm)


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


def clamp_trims(trim_s: float, trim_end_s: float, duration_s: float) -> tuple[float, float]:
    """Scale head/tail trims so a short clip keeps a usable remaining duration.

    Fingerprint trims are drawn from preset ranges that assume a typical social clip.
    On a 1s source, STRONG's 0.30–0.85s per end would otherwise consume the whole file.
    Long clips are unchanged: the cap only fires when start+end would leave less than
    max(50ms, half the duration), capped at 1s remaining.
    """
    start = max(0.0, float(trim_s))
    end = max(0.0, float(trim_end_s))
    if duration_s <= 0:
        return 0.0, 0.0
    remaining_floor = min(
        _REMAINING_CAP_S,
        max(_MIN_REMAINING_S, duration_s * _REMAINING_FRACTION),
        duration_s,
    )
    budget = max(0.0, duration_s - remaining_floor)
    total = start + end
    if total > budget and total > 0:
        scale = budget / total
        start *= scale
        end *= scale
    start = min(start, budget)
    end = min(end, max(0.0, duration_s - start - remaining_floor))
    return round(start, 4), round(end, 4)


def clamp_strength(strength: float) -> float:
    """Clamp `strength` to the range `sample()` honors.

    Capped at 2.0 (not 1.0): the uniqueness ladder escalates strength ABOVE 1.0 (e.g.
    1.0 -> 1.25 -> 1.5) to spend more of the budget on later rungs, and that only does
    anything if values above 1.0 are distinct from 1.0. Callers (e.g. pipeline.py) should
    use this to compute the EFFECTIVE strength before calling `sample`, so whatever they
    record as "the strength actually applied" matches what `sample` really used.
    """
    return min(2.0, max(0.0, strength))


def _remap_range(value: float, src: Range, dst: Range) -> float:
    """Map ``value`` from ``src`` onto ``dst`` (same seed position, new band)."""
    if src.lo == dst.lo and src.hi == dst.hi:
        return value
    span = src.hi - src.lo
    if span <= 0:
        return dst.lo
    t = min(1.0, max(0.0, (value - src.lo) / span))
    return dst.lo + t * (dst.hi - dst.lo)


def disable_fast_pixel_ops(params: dict) -> dict:
    """HQ skip: ESRGAN already rebuilds pixels. Zeros resample/rebuild/warp, keeps the rest."""
    video = dict(params["video"])
    video["resample_px"] = 0
    video["rebuild_scale"] = 1.0
    video["warp_k1"] = 0.0
    return {**params, "video": video}


def sample(
    preset: Preset,
    seed: int,
    *,
    rubberband: bool = False,
    strength: float = 1.0,
    duration_s: float | None = None,
    shot: str | None = None,
) -> dict:
    """Draw budgeted, zero-mean params for one variant.

    `strength` in [0, 2] is the lever the auto-tune controller / quality guard drives: it
    caps total distortion at `strength * preset.budget`. 1.0 spends the full budget; values
    above 1.0 push past the preset's nominal budget (used by the uniqueness ladder to make
    escalating rungs actually distinct); lower values yield gentler variants. The seed fixes
    WHICH axes move; strength fixes how far. `duration_s` (when given) scales head/tail
    trim so a short source keeps a usable remaining duration. `shot` is a look-first
    hint (`talking_head` / `motion`); None keeps the preset rebuild band so seeds match.
    """
    strength = clamp_strength(strength)
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

    raw["rebuild_scale"] = _remap_range(
        raw["rebuild_scale"], preset.rebuild_scale, rebuild_range_for_shot(preset, shot),
    )
    grain_draw = raw["grain"]

    # Fit the budget: shrink grain/unsharp/crf first so color shows.
    # crop_keep and rebuild_scale are unbudgeted fingerprints — strength must
    # not pull keep to 1.0 or rebuild to identity. Warp shrinks with look.
    spent = _spent_on(raw, preset, _ENCODE_AXES | _LOOK_AXES)
    if spent > budget and spent > 0:
        look_spent = _spent_on(raw, preset, _LOOK_AXES)
        leftover = budget - look_spent
        if leftover >= 0:
            enc_spent = _spent_on(raw, preset, _ENCODE_AXES)
            if enc_spent > 0:
                _shrink_toward_calm(raw, preset, _ENCODE_AXES, leftover / enc_spent)
        else:
            _shrink_toward_calm(raw, preset, _ENCODE_AXES, 0.0)
            look_spent = _spent_on(raw, preset, _LOOK_AXES)
            if look_spent > 0:
                _shrink_toward_calm(raw, preset, _LOOK_AXES, budget / look_spent)

    shot_grain = grain_range_for_shot(preset, shot)
    if shot_grain is not None:
        # Remap the *pre-shrink* draw onto the shot grain band so encode-first
        # budget shrink cannot pin talking-head uniqueness grain at strong.lo.
        raw["grain"] = _remap_range(grain_draw, preset.grain, shot_grain)

    # Fingerprint-only geometry axes: unbudgeted (never count toward distortion), drawn
    # independently of the shrink step above so a full-strength crop offset never eats
    # into the quality budget. crop_x_frac/crop_y_frac range over the whole frame
    # (zero-mean at the centered 0.5); trim_end_s reuses the preset's trim_s range,
    # drawn independently from trim_s (same distribution, different draw).
    raw["crop_x_frac"] = rng.uniform(0.0, 1.0)
    raw["crop_y_frac"] = rng.uniform(0.0, 1.0)
    raw["trim_end_s"] = rng.uniform(preset.trim_s.lo, preset.trim_s.hi)
    raw["resample_px"] = rng.choice(RESAMPLE_PX_CHOICES)
    raw["resample_flags"] = rng.choice(RESAMPLE_FLAGS)
    if duration_s is not None:
        raw["trim_s"], raw["trim_end_s"] = clamp_trims(
            raw["trim_s"], raw["trim_end_s"], duration_s,
        )

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
