"""Target platform profiles: resolution + fps. 'none' keeps source geometry.

Social canvases follow the source frame: 9:16 → 1080×1920, 16:9 → 1920×1080,
square → 1080×1080. Stretching landscape into portrait is a bug — uniqueness
then compares a letterboxed source to a squeezed variant and scores ~90%+
for free.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

# Constrained VBR ceiling for Reels/TikTok/Shorts. CRF still picks quality;
# maxrate stops temporal-grain bombs (~60 Mbps → 108 MB for an 8s clip).
# bufsize = 2× is the ffmpeg constrained-VBR convention. Not a CBR target.
SOCIAL_MAXRATE = "12M"
SOCIAL_BUFSIZE = "24M"
SOCIAL_LONG_EDGE = 1920
SOCIAL_SHORT_EDGE = 1080

ORIENT_LANDSCAPE = "landscape"
ORIENT_PORTRAIT = "portrait"
ORIENT_SQUARE = "square"


@dataclass(frozen=True)
class Platform:
    name: str
    width: int | None
    height: int | None
    fps: float | None
    maxrate: str | None = None
    bufsize: str | None = None


def x264_rate_args(platform: Platform) -> list[str]:
    """libx264 maxrate/bufsize argv, or empty when the platform is uncapped."""
    if not platform.maxrate:
        return []
    args = ["-maxrate", platform.maxrate]
    if platform.bufsize:
        args += ["-bufsize", platform.bufsize]
    return args


PLATFORMS = {
    "reels":  Platform("reels", 1080, 1920, 30.0, SOCIAL_MAXRATE, SOCIAL_BUFSIZE),
    "tiktok": Platform("tiktok", 1080, 1920, 30.0, SOCIAL_MAXRATE, SOCIAL_BUFSIZE),
    "shorts": Platform("shorts", 1080, 1920, 30.0, SOCIAL_MAXRATE, SOCIAL_BUFSIZE),
    "none":   Platform("none", None, None, None),
}


def get_platform(name: str) -> Platform:
    try:
        return PLATFORMS[name]
    except KeyError:
        raise ValueError(f"unknown platform {name!r}; choose from {sorted(PLATFORMS)}")


def frame_orientation(width: int | None, height: int | None) -> str:
    """Portrait / landscape / square from display size (probe already applies rotate)."""
    w = int(width or 0)
    h = int(height or 0)
    if w <= 0 or h <= 0:
        return ORIENT_PORTRAIT
    if w == h:
        return ORIENT_SQUARE
    return ORIENT_LANDSCAPE if w > h else ORIENT_PORTRAIT


def social_canvas(width: int | None, height: int | None) -> tuple[int, int]:
    """1080×1920 / 1920×1080 / 1080×1080 matching the source frame."""
    orient = frame_orientation(width, height)
    if orient == ORIENT_LANDSCAPE:
        return SOCIAL_LONG_EDGE, SOCIAL_SHORT_EDGE
    if orient == ORIENT_SQUARE:
        return SOCIAL_SHORT_EDGE, SOCIAL_SHORT_EDGE
    return SOCIAL_SHORT_EDGE, SOCIAL_LONG_EDGE


def resolve_platform(name: str, width: int | None = None, height: int | None = None) -> Platform:
    """Named profile with width/height flipped to the source orientation.

    ``none`` stays geometry-free. Social profiles keep fps + the 12M ceiling.
    """
    base = get_platform(name)
    if base.width is None or base.height is None:
        return base
    ow, oh = social_canvas(width, height)
    if (ow, oh) == (base.width, base.height):
        return base
    return replace(base, width=ow, height=oh)
