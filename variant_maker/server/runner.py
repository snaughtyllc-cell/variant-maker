"""Runner seam: 'render one source into N variants', abstracted so a GPU runner drops in.

LocalRunner wraps the in-process engine (pipeline.run, Tier-1 CPU). A future
RunPodServerlessRunner implements the same protocol against a serverless GPU endpoint.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Protocol

from .. import pipeline, uniqueness
from .events import VariantEvent

# Stage-1 LocalRunner defaults (see plan Global Constraints).
DEFAULT_PRESET = "medium"
DEFAULT_PLATFORM = "tiktok"   # vertical 1080x1920
DEFAULT_QUALITY_MODE = "fast"  # Tier-1 CPU, no GPU
MAX_REGEN = 3
# Top-tail gate: 24 bits ≈ 37.5% unique (TikFusion floor is ~18).
UNIQUENESS_TARGET = uniqueness.DEFAULT_TARGET
UNIQ_STRENGTHS = list(pipeline.DEFAULT_UNIQ_STRENGTHS)
MIN_BITS_VS_PEERS = uniqueness.MIN_PEER_BITS
ALLOW_CREATIVE_ESCALATE = True
HQ_UNIQ_STRENGTHS = [1.0]
HQ_MAX_REGEN = 1


def hq_job_limits(quality_mode: str) -> dict:
    """Per-mode job knobs. Fast gets auto-tune; HQ is one Real-ESRGAN pass."""
    if quality_mode == "hq":
        return {
            "uniq_strengths": list(HQ_UNIQ_STRENGTHS),
            "max_regen": HQ_MAX_REGEN,
            "allow_creative_escalate": False,
            "auto_tune": False,
        }
    return {"auto_tune": True}


def normalize_quality_mode(value: str | None, *, default: str = DEFAULT_QUALITY_MODE) -> str:
    if value is None:
        return default
    mode = str(value).strip().lower()
    return mode if mode in ("fast", "hq") else default


@dataclass
class VariantResult:
    index: int
    filename: str
    status: str
    quality: dict
    path: str
    uniqueness: float | None = None
    uniqueness_status: str | None = None
    uniqueness_metric: str | None = None
    uniqueness_target: float | None = None
    preset_used: str | None = None
    strength_final: float | None = None
    escalated: bool = False
    platform_result: str | None = None


@dataclass
class SourceResult:
    variants: list[VariantResult]
    manifest_path: str


class Runner(Protocol):
    def run(self, source_path: str, *, count: int, out_dir: str, source_id: str,
            on_event: Callable[[VariantEvent], None],
            allow_creative_escalate: bool = True,
            quality_mode: str = DEFAULT_QUALITY_MODE,
            cancel_token=None) -> SourceResult:
        ...


class LocalRunner:
    """In-process engine runner. Translates engine callbacks into VariantEvents."""

    def run(self, source_path: str, *, count: int, out_dir: str, source_id: str,
            on_event: Callable[[VariantEvent], None],
            allow_creative_escalate: bool = True,
            quality_mode: str = DEFAULT_QUALITY_MODE,
            cancel_token=None) -> SourceResult:
        def engine_event(state: str, **kw) -> None:
            on_event(VariantEvent(
                source_id=source_id,
                index=kw["index"],
                state=state,
                attempt=kw.get("attempt", 0),
                max_attempts=kw.get("max_attempts", 0),
                status=kw.get("status"),
                quality=kw.get("quality"),
                filename=kw.get("filename"),
                uniqueness=kw.get("uniqueness"),
                uniqueness_status=kw.get("uniqueness_status"),
                uniqueness_metric=kw.get("uniqueness_metric"),
                uniqueness_target=kw.get("uniqueness_target"),
                escalated=bool(kw.get("escalated", False)),
                preset_used=kw.get("preset_used"),
                strength_final=kw.get("strength_final"),
                platform_result=kw.get("platform_result"),
            ))

        quality_mode = normalize_quality_mode(quality_mode)
        limits = hq_job_limits(quality_mode)
        config = {
            "input": source_path,
            "out": out_dir,
            "count": count,
            "preset": DEFAULT_PRESET,
            "platform": DEFAULT_PLATFORM,
            "quality_mode": quality_mode,
            "max_regen": limits.get("max_regen", MAX_REGEN),
            "jobs": 1,
            "uniqueness_target": UNIQUENESS_TARGET,
            "uniq_strengths": limits.get("uniq_strengths", list(UNIQ_STRENGTHS)),
            "min_bits_vs_peers": MIN_BITS_VS_PEERS,
            "allow_creative_escalate": limits.get(
                "allow_creative_escalate", allow_creative_escalate,
            ),
            "auto_tune": limits.get("auto_tune", True),
            "cancel_token": cancel_token,
        }
        manifest = pipeline.run(config, on_event=engine_event)
        variants = [
            VariantResult(
                index=v.index, filename=v.filename, status=v.status,
                quality=v.quality, path=os.path.join(out_dir, v.filename),
                uniqueness=getattr(v, "uniqueness", None),
                uniqueness_status=getattr(v, "uniqueness_status", None),
                uniqueness_metric=getattr(v, "uniqueness_metric", None),
                uniqueness_target=getattr(v, "uniqueness_target", None),
                preset_used=getattr(v, "preset_used", None),
                strength_final=getattr(v, "strength_final", None),
                escalated=getattr(v, "escalated", False),
                platform_result=getattr(v, "platform_result", None),
            )
            for v in manifest.variants
        ]
        return SourceResult(variants=variants, manifest_path=os.path.join(out_dir, "manifest.json"))
