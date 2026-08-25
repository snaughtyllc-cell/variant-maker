"""Invite-only plan table: Fast/HQ caps and which Studio tabs a workspace sees.

Pure: no ffmpeg, no tenants I/O. Same inputs → same caps. Missing/unknown plan
is **internal** so Jeff's live workspace stays uncapped until he sets a plan.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PlanId = Literal["creator", "pro", "agency", "internal"]
QualityKind = Literal["fast", "hq"]

WINDOW_DAYS = 30
PLAN_IDS: tuple[PlanId, ...] = ("creator", "pro", "agency", "internal")

# Fast copies = delivered-or-reserved units (sources × copies) in a rolling window.
# HQ 0 on Creator: daily packs are Fast.
PLAN_TABLE: dict[PlanId, dict] = {
    "creator": {
        "fast_limit_30d": 200,  # 10 sources × 20 copies
        "hq_limit_30d": 0,
        "workflows": False,
        "team": False,
    },
    "pro": {
        "fast_limit_30d": 1000,
        "hq_limit_30d": 20,
        "workflows": True,
        "team": True,
    },
    "agency": {
        "fast_limit_30d": 3000,
        "hq_limit_30d": 80,
        "workflows": True,
        "team": True,
    },
    "internal": {
        "fast_limit_30d": None,
        "hq_limit_30d": None,
        "workflows": True,
        "team": True,
    },
}


def normalize_plan(raw: object) -> PlanId:
    if isinstance(raw, str):
        key = raw.strip().lower()
        if key in PLAN_TABLE:
            return key  # type: ignore[return-value]
    return "internal"


def fast_limit(plan: PlanId, override: int | None = None) -> int | None:
    if override is not None:
        return override
    return PLAN_TABLE[plan]["fast_limit_30d"]


def hq_limit(plan: PlanId, override: int | None = None) -> int | None:
    if override is not None:
        return override
    return PLAN_TABLE[plan]["hq_limit_30d"]


def shows_workflows(plan: PlanId) -> bool:
    return bool(PLAN_TABLE[plan]["workflows"])


def shows_team(plan: PlanId) -> bool:
    return bool(PLAN_TABLE[plan]["team"])


def quality_kind(quality_mode: str | None) -> QualityKind:
    return "hq" if (quality_mode or "").strip().lower() == "hq" else "fast"


@dataclass(frozen=True)
class QuotaSnapshot:
    plan: PlanId
    fast_used: int
    fast_limit: int | None
    hq_used: int
    hq_limit: int | None
    window_days: int = WINDOW_DAYS

    @property
    def fast_remaining(self) -> int | None:
        if self.fast_limit is None:
            return None
        return max(0, self.fast_limit - self.fast_used)

    @property
    def hq_remaining(self) -> int | None:
        if self.hq_limit is None:
            return None
        return max(0, self.hq_limit - self.hq_used)


def quota_message(
    *,
    kind: QualityKind,
    used: int,
    limit: int,
    need: int,
    window_days: int = WINDOW_DAYS,
) -> str:
    remaining = max(0, limit - used)
    if kind == "hq" and limit == 0:
        return (
            "HQ is not on this plan. Daily packs are Fast — ask Jeff if a clip needs HQ."
        )
    label = "Fast copies" if kind == "fast" else "HQ copies"
    return (
        f"You've used {used} / {limit} {label} in the last {window_days} days. "
        f"This run needs {need} and you have {remaining} left. "
        f"Batch sources in one Generate, or ask Jeff to bump the plan."
    )


def blocked_reason(snap: QuotaSnapshot, kind: QualityKind, need: int) -> str | None:
    if need <= 0:
        return None
    limit = snap.fast_limit if kind == "fast" else snap.hq_limit
    used = snap.fast_used if kind == "fast" else snap.hq_used
    if limit is None:
        return None
    if used + need <= limit:
        return None
    return quota_message(
        kind=kind, used=used, limit=limit, need=need, window_days=snap.window_days,
    )
