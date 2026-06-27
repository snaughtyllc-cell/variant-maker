"""Target platform profiles: resolution + fps. 'none' keeps source geometry."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Platform:
    name: str
    width: int | None
    height: int | None
    fps: float | None


PLATFORMS = {
    "reels":  Platform("reels", 1080, 1920, 30.0),
    "tiktok": Platform("tiktok", 1080, 1920, 30.0),
    "shorts": Platform("shorts", 1080, 1920, 30.0),
    "none":   Platform("none", None, None, None),
}


def get_platform(name: str) -> Platform:
    try:
        return PLATFORMS[name]
    except KeyError:
        raise ValueError(f"unknown platform {name!r}; choose from {sorted(PLATFORMS)}")
