"""Target platform profiles: resolution + fps. 'none' keeps source geometry."""
from __future__ import annotations

from dataclasses import dataclass, replace

# Constrained VBR ceiling for Reels/TikTok/Shorts. CRF still picks quality;
# maxrate stops temporal-grain bombs (~60 Mbps → 108 MB for an 8s clip).
# bufsize = 2× is the ffmpeg constrained-VBR convention. Not a CBR target.
SOCIAL_MAXRATE = "12M"
SOCIAL_BUFSIZE = "24M"


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


def _even_dim(n: int) -> int:
    n = int(n)
    return max(2, n - (n % 2))


def fit_platform_to_source(platform: Platform, width: int, height: int) -> Platform:
    """Fast: never naive-upscale. Keep source size when it already fits the canvas.

    HQ Real-ESRGAN still targets the full platform size. ``none`` is unchanged.
    libx264 needs even dims, so odd sources are floored to even before the fit.
    """
    if platform.width is None or platform.height is None:
        return platform
    try:
        sw, sh = _even_dim(width), _even_dim(height)
    except (TypeError, ValueError):
        return platform
    tw, th = int(platform.width), int(platform.height)
    if sw <= tw and sh <= th:
        return replace(platform, width=sw, height=sh)
    return platform
