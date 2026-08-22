"""Look-first shot probe for Fast.

Classify a source from ffmpeg self-similarity on the uniqueness canvas
(576×1024, 25% vs 75%). A talking-head barely moves between those frames;
a cinematic runner already disagrees with itself. That label is a hint for
`sample(shot=)` — not a platform detector, and not OpenCV face-protect.
"""
from __future__ import annotations

import os
import subprocess
import tempfile

from . import uniqueness
from .presets import Range

TALKING_HEAD_SELF_BITS = uniqueness.TARGET_BITS  # 24: source wouldn't pass vs itself
SHOT_TALKING_HEAD = "talking_head"
SHOT_MOTION = "motion"

# Look-first: motion already scores from movement, so rebuild stays gentle.
# Talking-head on the uniqueness canvas (576×1024) does NOT see reconstructive
# rebuild — AQMTp at 0.25–0.31 still scored 20–22 bits, and a local sweep of
# rebuild 0.27 matched identity encode (8 bits). Grain is what 576 scores:
# crop 0.86 + noise=alls=32/40/56 → 28/31/38 bits under the 12M cap.
# Grain 40–52 *luma* hit 37–39 bits (~58–61% UI) on lab but VMAF ~80
# (best_effort, harvest skip). SSIM All sees chroma; VMAF is mostly luma.
# Talking-head grain is chroma-only (noise_chroma). Local crop + chroma 40/56
# scored 35/43 bits (55/67% UI). Lab chroma 40/45/48 scored 40/43/44 bits
# (62/67/69% UI). Band 34–42 aims at typical 55–65% on *1080*.
# 720 SaveInta bench (2026-08-22): crop 0.86 + phone-safe c1s=14 → 26 bits
# (41%). Same + rebuild 0.73/0.67 → 24 bits (38%) — lanczos smooths the
# chroma 576 was scoring. c1s=27 → 37 bits (58%) — that IS the snow Jeff
# rejected. Scoring at native 720 / 1080 does not recover those bits.
# Do not remap talking-head onto preset rebuild to "buy" %. Do not clone
# Pixel AI scramble. Gate 24/24. Shrink does not collapse uniqueness grain
# to shot.lo when look overspends. No extra rotate (captions). Crop/warp
# stay on the preset.
# 720 chroma cloud: overlay at 80×142 (then bicubic back) hit 32 bits (50%)
# without snow when it REPLACED phone-safe grain. Lab pack 650f28dfb1f2
# stacked c1s 12–15 + cloud 18–22 → 42–46 bits / 66–72% and still read as
# snow. Filtergraph draws cloud instead of full-res chroma
# when the canvas short edge is under 1080. 1080 talking-head stays 34–42.
# Band 18–22 (n24 read as a green cast). Derived from grain — no extra RNG.
_REBUILD_FOR_SHOT = {
    ("subtle", SHOT_TALKING_HEAD): Range(0.94, 0.99),
    ("subtle", SHOT_MOTION): Range(0.94, 0.99),
    ("medium", SHOT_TALKING_HEAD): Range(0.90, 0.98),
    ("medium", SHOT_MOTION): Range(0.78, 0.90),
    ("strong", SHOT_TALKING_HEAD): Range(0.85, 0.94),
    ("strong", SHOT_MOTION): Range(0.67, 0.80),
}
_GRAIN_FOR_SHOT = {
    ("subtle", SHOT_TALKING_HEAD): Range(24, 36),
    ("medium", SHOT_TALKING_HEAD): Range(34, 42),
    ("strong", SHOT_TALKING_HEAD): Range(46, 58),
}
_CHROMA_CLOUD_FOR_SHOT = Range(18, 22)


def rebuild_range_for_shot(preset, shot: str | None) -> Range:
    """Return the rebuild_scale range `sample()` should draw for this shot."""
    if not shot:
        return preset.rebuild_scale
    return _REBUILD_FOR_SHOT.get((preset.name, shot), preset.rebuild_scale)


def grain_range_for_shot(preset, shot: str | None) -> Range | None:
    """Talking-head grain band, or None to keep the budgeted draw."""
    if not shot:
        return None
    return _GRAIN_FOR_SHOT.get((preset.name, shot))


def chroma_cloud_range_for_shot(preset, shot: str | None) -> Range | None:
    """Low-res chroma overlay band for talking-head, or None to skip."""
    if grain_range_for_shot(preset, shot) is None:
        return None
    return _CHROMA_CLOUD_FOR_SHOT


def _duration(path: str, given: float | None) -> float:
    if given is not None and given > 0:
        return float(given)
    return uniqueness._probe_duration(path)


def classify_shot(path: str, duration_s: float | None = None) -> dict:
    """`talking_head` if 25% vs 75% self-bits < 24, else `motion`.

    Missing file or ffmpeg failure → kind=None so the pack keeps the default recipe.
    """
    if not path or not os.path.isfile(path):
        return {"kind": None, "self_bits": None}
    try:
        dur = _duration(path, duration_s)
        with tempfile.TemporaryDirectory(prefix="vm-shot-") as tmp:
            fa = os.path.join(tmp, "a.png")
            fb = os.path.join(tmp, "b.png")
            uniqueness._extract_frame(path, 0.25 * dur, fa)
            uniqueness._extract_frame(path, 0.75 * dur, fb)
            self_bits = uniqueness.bits_from_ssim(uniqueness._ssim_pair(fa, fb))
    except (OSError, ValueError, subprocess.CalledProcessError):
        return {"kind": None, "self_bits": None}
    kind = SHOT_TALKING_HEAD if self_bits < TALKING_HEAD_SELF_BITS else SHOT_MOTION
    return {"kind": kind, "self_bits": int(self_bits)}
