"""Durable Fast occupancy journal — restart must not free a live slot."""
from __future__ import annotations

from variant_maker.server.occupancy_journal import OccupancyJournal


def _journal(tmp_path) -> OccupancyJournal:
    return OccupancyJournal(str(tmp_path / "fast_occupancy.json"), n_slots=2)


def test_occupy_and_release_are_fenced(tmp_path):
    j = _journal(tmp_path)
    rec = j.occupy(
        0,
        tenant_id="ws_a",
        job_id="job_a",
        attempt_id="att1",
        fence="fence-a",
        provider_job_id="rp1",
    )
    assert rec.state == "occupied"
    assert j.release(0, fence="wrong") is False
    assert j.snapshot()["slots"][0]["job_id"] == "job_a"
    assert j.release(0, fence="fence-a") is True
    assert j.snapshot()["slots"][0]["state"] == "idle"
    assert j.snapshot()["slots"][0]["job_id"] is None


def test_restart_marks_occupied_unknown_and_pauses_dispatch(tmp_path):
    j = _journal(tmp_path)
    j.occupy(0, tenant_id="ws_a", job_id="job_a", attempt_id="a", fence="f", provider_job_id="rp1")
    j2 = OccupancyJournal(str(tmp_path / "fast_occupancy.json"), n_slots=2)
    snap = j2.on_process_start()
    assert snap["pause_dispatch"] is True
    assert snap["slots"][0]["state"] == "unknown"
    assert snap["slots"][0]["job_id"] == "job_a"
    assert snap["slots"][0]["provider_job_id"] == "rp1"
    assert j2.can_dispatch() is False


def test_reconcile_keeps_slot_when_provider_still_running(tmp_path):
    j = _journal(tmp_path)
    j.occupy(0, tenant_id="ws_a", job_id="job_a", attempt_id="a", fence="f", provider_job_id="rp1")
    j.on_process_start()
    snap = j.reconcile(running_provider_ids={"rp1"})
    assert snap["slots"][0]["state"] == "occupied"
    assert snap["pause_dispatch"] is False
    assert j.can_dispatch() is True


def test_reconcile_frees_slot_only_when_provider_confirms_gone(tmp_path):
    j = _journal(tmp_path)
    j.occupy(0, tenant_id="ws_a", job_id="job_a", attempt_id="a", fence="f", provider_job_id="rp1")
    j.on_process_start()
    snap = j.reconcile(running_provider_ids=set())
    assert snap["slots"][0]["state"] == "idle"
    assert snap["slots"][0]["job_id"] is None
    assert snap["pause_dispatch"] is False


def test_untracked_provider_job_keeps_dispatch_paused(tmp_path):
    j = _journal(tmp_path)
    j.on_process_start()
    snap = j.reconcile(running_provider_ids={"rp-orphan"})
    assert snap["pause_dispatch"] is True
    assert j.can_dispatch() is False


def test_unknown_without_provider_id_stays_paused(tmp_path):
    j = _journal(tmp_path)
    j.occupy(1, tenant_id="ws_b", job_id="job_b", attempt_id="b", fence="g", provider_job_id=None)
    j.on_process_start()
    snap = j.reconcile(running_provider_ids=set())
    assert snap["slots"][1]["state"] == "unknown"
    assert snap["pause_dispatch"] is True
