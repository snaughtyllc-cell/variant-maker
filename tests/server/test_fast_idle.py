"""Fast CPU idle / scale-to-zero policy — no primer until measured, no HQ occupancy."""
from __future__ import annotations

from variant_maker.server.fast_idle import (
    FAST_IDLE_TIMEOUT_S,
    FAST_MAX_WORKERS,
    FAST_MIN_WORKERS,
    KIND_PRIMER,
    STATE_IDLE,
    STATE_OCCUPIED,
    STATE_UNKNOWN,
    billed_parts,
    classify_start,
    primer_disposition,
    should_reset_idle_timer,
    should_start_primer,
    takes_studio_lock,
)


def test_endpoint_defaults_are_min0_max2_idle_120():
    assert FAST_MIN_WORKERS == 0
    assert FAST_MAX_WORKERS == 2
    assert FAST_IDLE_TIMEOUT_S == 120


def test_heartbeat_does_not_reset_idle_timer():
    assert should_reset_idle_timer("heartbeat") is False
    assert should_reset_idle_timer("health") is False
    assert should_reset_idle_timer("work_start") is True
    assert should_reset_idle_timer("work_progress") is True
    assert should_reset_idle_timer("upload") is True
    assert should_reset_idle_timer("cleanup") is True


def test_missing_heartbeat_is_unknown_not_idle():
    assert STATE_UNKNOWN != STATE_IDLE
    assert STATE_OCCUPIED != STATE_IDLE


def test_primer_disabled_by_default():
    assert should_start_primer(
        primer_enabled=False,
        real_job_queued=False,
        any_slot_busy=False,
        primer_already_active=False,
        worker_warm=False,
    ) == "disabled"


def test_primer_skips_when_real_work_or_warm_worker_exists():
    kwargs = {"primer_enabled": True, "primer_already_active": False}
    assert should_start_primer(real_job_queued=True, any_slot_busy=False, worker_warm=False, **kwargs) == "real_queued"
    assert should_start_primer(real_job_queued=False, any_slot_busy=True, worker_warm=False, **kwargs) == "slot_busy"
    assert should_start_primer(real_job_queued=False, any_slot_busy=False, worker_warm=True, **kwargs) == "already_warm"
    assert should_start_primer(
        real_job_queued=False, any_slot_busy=False, worker_warm=False,
        primer_already_active=True, primer_enabled=True,
    ) == "primer_active"
    assert should_start_primer(
        real_job_queued=False, any_slot_busy=False, worker_warm=False, primer_enabled=True,
        primer_already_active=False,
    ) == "ok"


def test_primer_does_not_take_studio_lock():
    assert takes_studio_lock("fast") is True
    assert takes_studio_lock(KIND_PRIMER) is False


def test_real_job_supersedes_queued_primer():
    assert primer_disposition("queued") == "remove"
    assert primer_disposition("booting") == "supersede"
    assert primer_disposition("encoding") == "cancel_then_release"


def test_classify_start_cold_warm_unknown():
    cold = classify_start(statuses=["IN_QUEUE", "IN_PROGRESS"], worker_id="w1", boot_id="b1")
    assert cold["classification"] == "cold"
    assert cold["worker_id"] == "w1"
    assert cold["boot_id"] == "b1"
    assert cold["flashboot"] is None

    warm = classify_start(statuses=["IN_PROGRESS"], worker_id="w2", flashboot=True)
    assert warm["classification"] == "warm"
    assert warm["flashboot"] is True

    unknown = classify_start(statuses=[], worker_id=None)
    assert unknown["classification"] == "unknown"
    assert unknown["flashboot"] is None


def test_billed_parts_split_real_primer_idle():
    parts = billed_parts(work_s=90, idle_s=120, primer_s=12)
    assert parts["real_work_s"] == 90
    assert parts["primer_work_s"] == 12
    assert parts["idle_retention_s"] == 120
    assert parts["total_s"] == 222
