"""Shared dataclasses. Pure. No ffmpeg, no Lab."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Slot = Literal["top", "mid", "low"]
SLOTS: tuple[Slot, ...] = ("top", "mid", "low")
SAFE_SLOTS: tuple[Slot, ...] = ("top", "low")

# y as a fraction of frame height for Alignment=8 (top-center) MarginV.
SLOT_Y: dict[Slot, float] = {
    "top": 0.16,
    "mid": 0.45,
    "low": 0.62,
}

StyleId = Literal["tiktok-classic-box", "edits-classic-outline", "edits-strong"]
STYLE_IDS: tuple[StyleId, ...] = (
    "tiktok-classic-box",
    "edits-classic-outline",
    "edits-strong",
)


@dataclass(frozen=True)
class StylePreset:
    id: str
    font_file: str
    font_name: str
    size_frac: float
    primary_ass: str
    outline_ass: str
    back_ass: str
    outline: float
    shadow: float
    box: bool
    max_lines: int
    max_width_frac: float
    bold: bool = False


@dataclass(frozen=True)
class HookParams:
    index: int
    text: str
    style_id: str
    slot: Slot
    source: str = "expand"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OverlayPlan:
    seed_text: str
    count: int
    master_seed: str
    hooks: list[HookParams] = field(default_factory=list)
    locked: bool = False
    source_text: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed_text": self.seed_text,
            "count": self.count,
            "master_seed": self.master_seed,
            "locked": self.locked,
            "source_text": self.source_text,
            "hooks": [h.to_dict() for h in self.hooks],
        }


@dataclass(frozen=True)
class VideoInfo:
    path: str
    width: int
    height: int
    duration_s: float
    fps: float
    has_audio: bool
