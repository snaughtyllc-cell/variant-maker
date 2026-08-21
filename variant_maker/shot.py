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

# Heavier rebuild for still faces; gentler for clips that already score from motion.
# Crop/grain/warp stay on the preset. Gate stays 24/24.
_REBUILD_FOR_SHOT = {
    ("subtle", SHOT_TALKING_HEAD): Range(0.80, 0.90),
    ("subtle", SHOT_MOTION): Range(0.94, 0.99),
    ("medium", SHOT_TALKING_HEAD): Range(0.50, 0.66),
    ("medium", SHOT_MOTION): Range(0.78, 0.90),
    ("strong", SHOT_TALKING_HEAD): Range(0.38, 0.49),
    ("strong", SHOT_MOTION): Range(0.67, 0.80),
}


def rebuild_range_for_shot(preset, shot: str | None) -> Range:
    """Return the rebuild_scale range `sample()` should draw for this shot."""
    if not shot:
        return preset.rebuild_scale
    return _REBUILD_FOR_SHOT.get((preset.name, shot), preset.rebuild_scale)


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
