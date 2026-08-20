"""Preset range tables (data, not logic) + the per-variant distortion budget.

Color shifts are ZERO-MEAN (a (lo, hi) range straddling neutral) so we never
systematically desaturate/darken — that systematic degradation IS the cheap look.
The sampler draws each axis from these ranges, then scales them down to fit `budget`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Range:
    lo: float
    hi: float


@dataclass(frozen=True)
class Preset:
    name: str
    budget: float  # total normalized distortion allowed across all axes (0..1 per axis)
    # video (zero-mean unless noted)
    crop_keep: Range
    rotate_deg: Range
    brightness: Range
    contrast: Range
    saturation: Range
    gamma: Range
    hue_deg: Range
    grain: Range
    unsharp: Range
    warp_k1: Range  # Fast pixel seed (lenscorrection); zero-mean; VMAF sees it
    speed: Range
    trim_s: Range
    crf: Range
    gop_choices: tuple[int, ...]
    # audio
    loudnorm_i: Range
    eq_gain_db: Range
    eq_bands: int
    pitch_pct: Range  # 0 unless rubberband available
    aac_kbps: Range


SUBTLE = Preset(
    name="subtle", budget=0.35,
    crop_keep=Range(0.98, 1.00), rotate_deg=Range(0.0, 0.0),
    brightness=Range(-0.01, 0.01), contrast=Range(0.99, 1.01),
    saturation=Range(0.99, 1.02), gamma=Range(0.99, 1.01),     hue_deg=Range(-1, 1),
    grain=Range(3, 6), unsharp=Range(0.0, 0.0), warp_k1=Range(-0.004, 0.004),
    speed=Range(0.99, 1.01),
    trim_s=Range(0.0, 0.10), crf=Range(18, 20), gop_choices=(48, 60),
    loudnorm_i=Range(-14, -14), eq_gain_db=Range(-1, 1), eq_bands=1,
    pitch_pct=Range(0.0, 0.0), aac_kbps=Range(160, 160),
)

MEDIUM = Preset(
    name="medium", budget=0.65,
    # Geometry sized so talking-head Fast lands ~32–38 SSIM bits (~50–60% UI)
    # without raising the 24-bit gate (that gate previously escalated 20-packs).
    crop_keep=Range(0.86, 0.94), rotate_deg=Range(-0.8, 0.8),
    brightness=Range(-0.025, 0.025), contrast=Range(0.97, 1.03),
    saturation=Range(0.96, 1.05), gamma=Range(0.97, 1.03),     hue_deg=Range(-3, 3),
    grain=Range(7, 14), unsharp=Range(0.2, 0.35), warp_k1=Range(-0.012, 0.012),
    speed=Range(0.96, 1.04),
    trim_s=Range(0.15, 0.50), crf=Range(19, 22), gop_choices=(48, 60, 90),
    loudnorm_i=Range(-15, -13), eq_gain_db=Range(-2, 2), eq_bands=2,
    pitch_pct=Range(-2.0, 2.0), aac_kbps=Range(128, 192),
)

STRONG = Preset(
    name="strong", budget=0.90,
    # Creative escalate: geometric push sized for ≥24 bits when light ladder stalls.
    crop_keep=Range(0.80, 0.92), rotate_deg=Range(-2.0, 2.0),
    brightness=Range(-0.04, 0.04), contrast=Range(0.95, 1.06),
    saturation=Range(0.92, 1.10), gamma=Range(0.95, 1.05),     hue_deg=Range(-6, 6),
    grain=Range(14, 22), unsharp=Range(0.3, 0.45), warp_k1=Range(-0.016, 0.016),
    speed=Range(0.94, 1.06),
    trim_s=Range(0.30, 0.85), crf=Range(20, 23), gop_choices=(60, 90, 120),
    loudnorm_i=Range(-16, -13), eq_gain_db=Range(-3, 3), eq_bands=2,
    pitch_pct=Range(-4.0, 4.0), aac_kbps=Range(128, 192),
)

PRESETS = {p.name: p for p in (SUBTLE, MEDIUM, STRONG)}


def get_preset(name: str) -> Preset:
    try:
        return PRESETS[name]
    except KeyError:
        raise ValueError(f"unknown preset {name!r}; choose from {sorted(PRESETS)}")
