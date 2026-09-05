"""Manifest = the reproduction contract and the bridge to any future detector.

Per-variant we store the exact recipe, the exact ffmpeg command, quality metrics, and a
`platform_result` slot. Test a batch on the real platform, drop in 'pass'/'fail', and you
have labeled `recipe -> outcome` data for free — all a later local detector would need.
"""
from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field, asdict


@dataclass
class VariantRecord:
    index: int
    filename: str
    seed: int
    params: dict
    ffmpeg_cmd: str
    tier: int = 1
    neural_ops: list = field(default_factory=list)
    quality: dict = field(default_factory=dict)
    output_sha256: str | None = None
    duration_s: float | None = None
    status: str = "ok"
    # None | "passed" | "duplicate_reject" | "unknown" — the detector bridge
    platform_result: str | None = None
    # Live permalink the VA pasted after posting (not a Drive file id).
    post_url: str | None = None
    uniqueness: float | None = None
    uniqueness_status: str | None = None  # ok|below_target|below_floor|unknown
    uniqueness_metric: str | None = None
    uniqueness_target: float | None = None
    preset_used: str | None = None
    strength_final: float | None = None
    escalated: bool = False
    look_status: str | None = None
    look_mae: float | None = None
    look_mae_max: float | None = None
    look_src: str | None = None
    look_var: str | None = None
    look_frames: list = field(default_factory=list)
    look_artifact_sha256: str | None = None
    look_approved_sha256: str | None = None
    look_review_t: float | None = None


@dataclass
class Manifest:
    source: dict
    run: dict
    variants: list = field(default_factory=list)
    tool: str = "variant-maker"
    version: str = "0.2.0"
    created_utc: str = field(
        default_factory=lambda: _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "version": self.version,
            "created_utc": self.created_utc,
            "source": self.source,
            "run": self.run,
            "variants": [asdict(v) for v in self.variants],
        }

    def write(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
