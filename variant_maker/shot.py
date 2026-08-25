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
# to shot.lo when look overspends. No extra rotate (captions).
# Instagram 720 talking-head: centered keep 0.92–0.96 scores 20–21 bits
# (below the gate). Punch leftover from the top (crop_y → 1.0) and keep
# 0.86–0.90 so crop-only clears 24 without eating burned-in words and
# without face-zoom 0.72/0.78. 1080 keeps the signed caption-safe band.
# 720 chroma cloud: overlay at 80×142 then bicubic back. Lab `650f28dfb1f2`
# stacked phone grain + cloud 18–22 (snow). `6d3e91ab7fd4` drew cloud-only
# 18–22 — still grain on the face. `8df4cc4` 6–10 + gblur 2 was better than
# those, but live SaveInta still read as chroma. Band is 4–7; filtergraph
# caps at 7 and gblurs sigma=4. Soft cloud on SaveInta (`softestd3ce5`)
# landed 24/24 bits (38%) — look approved, uniqueness too low. 720 luma
# dust 14–20 (c0s 15–17 on `softdust815a`) read as a little much. 8–12
# (`quietdustmed`, c0s=9) was usable but scored 23 bits. Band is 11–13
# so copies sit near c0s=12 to clear the 24-bit gate without redrawing
# 15–17. Filtergraph caps leftover 14–20 at 13. Luma-only, not stacked c1s.
# 1080 talking-head stays 34–42. Derived from grain — no extra RNG.
# Gate stays 24. Do not expect 55% on a still 720 face. AQMTp-class tight
# 720 faces stay 17–21 on signed medium; strong escalate draws a low-freq
# luma shade (8×14, gblur 12, c0s 94–100) so the uniqueness loop can clear
# 24 without snow or a cookie mesh. Medium stays shade-off (SaveInta).
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
_CHROMA_CLOUD_FOR_SHOT = Range(4, 7)
# 720-calibrated luma. Unscaled 14–20 (`softdust815a` c0s 15–17) was a
# little much. 8–12 (`quietdustmed` c0s=9) was usable but 23 bits. 11–13
# aims at the 24-bit gate. Luma-only so we do not restack c1s 12–15 snow.
_LUMA_DUST_FOR_SHOT = Range(11, 13)
# Strong 720 talking-head only. Lossless 8×14 c0s=90 + signed cloud/dust
# scored 24; veryfast x264 smoothed milder draws to 22. Band sits at the
# encode-surviving end. Medium is shade-off (SaveInta).
_LUMA_SHADE_720_TH = {
    "strong": Range(94, 100),
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


def chroma_cloud_range_for_shot(preset, shot: str | None) -> Range | None:
    """Low-res chroma overlay band for talking-head, or None to skip."""
    if grain_range_for_shot(preset, shot) is None:
        return None
    return _CHROMA_CLOUD_FOR_SHOT


def luma_dust_range_for_shot(preset, shot: str | None) -> Range | None:
    """720 talking-head luma dust band, or None to skip (motion / no shot)."""
    if grain_range_for_shot(preset, shot) is None:
        return None
    return _LUMA_DUST_FOR_SHOT


def luma_shade_range_for_shot(
    preset, shot: str | None, width: int | None = None, height: int | None = None,
) -> Range | None:
    """Strong 720 talking-head uniqueness lighting, or None (medium / 1080 / motion)."""
    if shot != SHOT_TALKING_HEAD or not is_phone_canvas(width, height):
        return None
    return _LUMA_SHADE_720_TH.get(preset.name)


# Instagram downloads land at 720. Centered caption-safe keep 0.92–0.96 scores
# 20–21 SSIM bits on that SKU (timed portrait.mp4) — below the 24-bit gate.
# Punch leftover from the TOP (y→1.0) so burned-in words stay; restore enough
# keep that crop-only clears 24. 1080 keeps the signed 0.92–0.96 / y 0.35–0.65
# band. Not face-zoom 0.72/0.78.
PHONE_SHORT_SIDE = 1080
_CROP_KEEP_720_TH = {
    "subtle": Range(0.94, 0.98),
    "medium": Range(0.86, 0.90),
    "strong": Range(0.82, 0.88),
}


def is_phone_canvas(width: int | None, height: int | None) -> bool:
    """True for Instagram-class 720 (or any source whose short side is under 1080)."""
    w, h = int(width or 0), int(height or 0)
    return w > 0 and h > 0 and min(w, h) < PHONE_SHORT_SIDE


def crop_keep_range_for_shot(
    preset, shot: str | None, width: int | None = None, height: int | None = None,
) -> Range | None:
    """720 talking-head uniqueness punch, or None to keep the preset (1080 / motion)."""
    if shot != SHOT_TALKING_HEAD or not is_phone_canvas(width, height):
        return None
    return _CROP_KEEP_720_TH.get(preset.name)


def keeps_bottom_captions(width: int | None = None, height: int | None = None) -> bool:
    """Instagram 720: take the crop leftover from the top so captions stay."""
    return is_phone_canvas(width, height)


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
