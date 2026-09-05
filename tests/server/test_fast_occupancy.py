"""Process-wide Fast occupancy — two scale-to-zero slots, one pack per worker."""
from __future__ import annotations

import threading

from variant_maker.server.fast_occupancy import FastOccupancy


def test_idle_slot_takes_the_incoming_pack():
    occ = FastOccupancy(fast_slots=2, endpoint_ids=["ep-a", "ep-b"])
    a = occ.try_begin("ws_a", "job_a", need_fast_slot=True)
    assert a is not None
    assert a.slot == 0
    assert a.endpoint_id == "ep-a"
    assert a.fence


def test_second_studio_gets_overflow_slot_not_the_same_worker():
    occ = FastOccupancy(fast_slots=2, endpoint_ids=["ep-a", "ep-b"])
    a = occ.try_begin("ws_a", "job_a", need_fast_slot=True)
    b = occ.try_begin("ws_b", "job_b", need_fast_slot=True)
    assert a is not None and b is not None
    assert {a.slot, b.slot} == {0, 1}
    assert {a.endpoint_id, b.endpoint_id} == {"ep-a", "ep-b"}


def test_same_studio_second_pack_queues_even_if_a_slot_is_free():
    occ = FastOccupancy(fast_slots=2)
    first = occ.try_begin("ws_a", "job_1", need_fast_slot=True)
    assert first is not None
    assert occ.try_begin("ws_a", "job_2", need_fast_slot=True) is None


def test_third_studio_waits_when_both_fast_slots_are_busy():
    occ = FastOccupancy(fast_slots=2)
    assert occ.try_begin("ws_a", "a", need_fast_slot=True)
    assert occ.try_begin("ws_b", "b", need_fast_slot=True)
    assert occ.try_begin("ws_c", "c", need_fast_slot=True) is None


def test_hq_does_not_consume_a_fast_slot():
    occ = FastOccupancy(fast_slots=2)
    hq = occ.try_begin("ws_a", "hq1", need_fast_slot=False)
    fast = occ.try_begin("ws_b", "fast1", need_fast_slot=True)
    assert hq is not None and hq.slot is None
    assert fast is not None and fast.slot == 0


def test_release_returns_slot_and_stale_fence_cannot_steal_it():
    occ = FastOccupancy(fast_slots=2)
    a = occ.try_begin("ws_a", "job_a", need_fast_slot=True)
    assert a is not None
    assert occ.release(a) is True
    b = occ.try_begin("ws_b", "job_b", need_fast_slot=True)
    assert b is not None
    assert b.slot == 0
    assert occ.release(a) is False  # stale fence
    assert occ.snapshot()["fast_slots"][0]["job_id"] == "job_b"


def test_simultaneous_claims_cannot_share_a_slot():
    occ = FastOccupancy(fast_slots=1)
    got: list = []

    def claim(tenant, job):
        got.append(occ.try_begin(tenant, job, need_fast_slot=True))

    t1 = threading.Thread(target=claim, args=("ws_a", "a"))
    t2 = threading.Thread(target=claim, args=("ws_b", "b"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    winners = [r for r in got if r is not None]
    assert len(winners) == 1
    assert sum(1 for r in got if r is None) == 1


def test_same_job_upgrades_studio_lock_to_fast_slot():
    occ = FastOccupancy(fast_slots=2, endpoint_ids=["ep-a", "ep-b"])
    hq = occ.try_begin("ws", "j1", need_fast_slot=False)
    assert hq is not None and hq.slot is None
    fast = occ.try_begin("ws", "j1", need_fast_slot=True)
    assert fast is not None and fast.slot == 0
    assert fast.endpoint_id == "ep-a"
    assert fast.fence != hq.fence
    assert occ.release(hq) is False
    assert occ.snapshot()["fast_slots"][0]["job_id"] == "j1"
    assert occ.release(fast) is True
    assert occ.snapshot()["fast_slots"][0] is None


def test_retry_keeps_job_id_but_issues_a_new_fence():
    occ = FastOccupancy(fast_slots=2)
    first = occ.try_begin("ws", "job", need_fast_slot=True)
    retry = occ.try_begin("ws", "job", need_fast_slot=True)
    assert first is not None and retry is not None
    assert first.job_id == retry.job_id == "job"
    assert first.slot == retry.slot == 0
    assert first.fence != retry.fence
    assert first.attempt_id != retry.attempt_id
    assert occ.release(first) is False
    assert occ.release(retry) is True


def test_occupancy_from_env_shares_primary_when_overflow_unset(monkeypatch):
    from variant_maker.server.fast_occupancy import occupancy_from_env

    monkeypatch.setenv("RUNPOD_FAST_ENDPOINT_ID", "ep-fast")
    monkeypatch.delenv("RUNPOD_FAST_ENDPOINT_ID_2", raising=False)
    occ = occupancy_from_env()
    a = occ.try_begin("a", "ja", need_fast_slot=True)
    b = occ.try_begin("b", "jb", need_fast_slot=True)
    assert a is not None and b is not None
    assert a.endpoint_id == b.endpoint_id == "ep-fast"
    assert {a.slot, b.slot} == {0, 1}
