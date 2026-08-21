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
# crop 0.86 + noise=alls=32/40/56 → 28/31/38 bits (44/48/59% UI) under the
# 12M cap. Rotate is skipped (captions go crooked). Crop/warp stay on the
# preset. Gate stays 24/24.
_REBUILD_FOR_SHOT = {
    ("subtle", SHOT_TALKING_HEAD): Range(0.94, 0.99),
    ("subtle", SHOT_MOTION): Range(0.94, 0.99),
    ("medium", SHOT_TALKING_HEAD): Range(0.90, 0.98),
    ("medium", SHOT_MOTION): Range(0.78, 0.90),
    ("strong", SHOT_TALKING_HEAD): Range(0.85, 0.94),
    ("strong", SHOT_MOTION): Range(0.67, 0.80),
}
_GRAIN_FOR_SHOT = {
    ("subtle", SHOT_TALKING_HEAD): Range(20, 28),
    ("medium", SHOT_TALKING_HEAD): Range(40, 52),
    ("strong", SHOT_TALKING_HEAD): Range(48, 60),
}


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
