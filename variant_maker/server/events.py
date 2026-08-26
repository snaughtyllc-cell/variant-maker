"""The progress contract: one event per variant state transition."""
from __future__ import annotations

from dataclasses import asdict, dataclass

# Valid VariantEvent.state values, in lifecycle order.
STATES = ("rendering", "checking", "looking", "rerolling", "uniqueness", "escalating", "done")


@dataclass
class VariantEvent:
    source_id: str
    index: int
    state: str
    attempt: int = 0          # rerolling: which retry (1..max_attempts)
    max_attempts: int = 0
    status: str | None = None     # done: "ok" | "best_effort" | "corrupt" | "uniqueness_fail"
    quality: dict | None = None   # done: vmaf/histogram_ok/spatial_ok/regen_count
    filename: str | None = None   # done: rendered file name
    # done: uniqueness meters — must travel with progressive polls, not only final replace.
    uniqueness: float | None = None
    uniqueness_status: str | None = None
    uniqueness_metric: str | None = None
    uniqueness_target: float | None = None
    escalated: bool = False
    preset_used: str | None = None
    strength_final: float | None = None
    platform_result: str | None = None
    look_status: str | None = None
    look_mae: float | None = None
    look_src: str | None = None
    look_var: str | None = None


def event_to_dict(e: VariantEvent) -> dict:
    """JSON-safe dict for SSE/data payloads."""
    return asdict(e)
