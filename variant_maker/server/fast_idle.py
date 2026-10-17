"""Fast CPU idle / scale-to-zero policy.

PURE: no ffmpeg, no RunPod. Encodes the Wave 2 ops contract:

- min workers 0, max 2, 120s idle timeout as the first experiment
- health heartbeats never reset the idle timer
- primer is off until measurement says FlashBoot + idle is not enough
- primer never takes a studio's one-job lock
- HQ GPU occupancy is out of scope

RunPod dashboard settings (FlashBoot, idle timeout, max workers) live in
``docs/ops/railway-studio.md``. This module is the in-process rules.
"""
from __future__ import annotations

FAST_MIN_WORKERS = 0
FAST_MAX_WORKERS = 2
FAST_IDLE_TIMEOUT_S = 120

STATE_OCCUPIED = "occupied"
STATE_IDLE = "idle"
STATE_UNKNOWN = "unknown"

KIND_FAST = "fast"
KIND_PRIMER = "primer"

_WORK_EVENTS = frozenset({"work_start", "work_progress", "upload", "cleanup", "cancel_cleanup"})
_HEALTH_EVENTS = frozenset({"heartbeat", "health"})

PRIMER_DISPOSITION = {
    "queued": "remove",
    "booting": "supersede",
    "encoding": "cancel_then_release",
}


def should_reset_idle_timer(event: str) -> bool:
    """Only actual work resets idle. Health heartbeats must not."""
    name = str(event or "").strip().lower()
    if name in _HEALTH_EVENTS:
        return False
    return name in _WORK_EVENTS


def takes_studio_lock(kind: str) -> bool:
    """A primer counts toward the two Fast slots but not a studio's one-job cap."""
    return str(kind or KIND_FAST).strip().lower() != KIND_PRIMER


def should_start_primer(
    *,
    primer_enabled: bool = False,
    real_job_queued: bool,
    any_slot_busy: bool,
    worker_warm: bool,
    primer_already_active: bool,
) -> str:
    """Return ``ok`` or a skip reason. Default is disabled until we measure."""
    if not primer_enabled:
        return "disabled"
    if primer_already_active:
        return "primer_active"
    if real_job_queued:
        return "real_queued"
    if any_slot_busy:
        return "slot_busy"
    if worker_warm:
        return "already_warm"
    return "ok"


def primer_disposition(primer_state: str) -> str:
    """What to do with a primer when a real job arrives."""
    key = str(primer_state or "").strip().lower()
    return PRIMER_DISPOSITION.get(key, "cancel_then_release")


def classify_start(
    *,
    statuses: list[str],
    worker_id: str | None = None,
    boot_id: str | None = None,
    flashboot: bool | None = None,
) -> dict:
    """Cold / warm / unknown from provider poll statuses. FlashBoot is separate."""
    seen = [str(s or "").strip().upper() for s in statuses if str(s or "").strip()]
    if "IN_QUEUE" in seen and "IN_PROGRESS" in seen:
        classification = "cold"
    elif seen and seen[0] == "IN_PROGRESS" and "IN_QUEUE" not in seen:
        classification = "warm"
    else:
        classification = "unknown"
    return {
        "classification": classification,
        "worker_id": worker_id,
        "boot_id": boot_id,
        "flashboot": flashboot,
    }


def billed_parts(
    *,
    work_s: float = 0.0,
    idle_s: float = 0.0,
    primer_s: float = 0.0,
) -> dict:
    real = max(0.0, float(work_s or 0.0))
    idle = max(0.0, float(idle_s or 0.0))
    primer = max(0.0, float(primer_s or 0.0))
    return {
        "real_work_s": real,
        "primer_work_s": primer,
        "idle_retention_s": idle,
        "total_s": real + idle + primer,
    }
