"""JobStore occupancy: two Fast slots, one live pack per studio, isolation keys."""
from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable

from tests.server.fakes import FakeObjectStore, FakeRunner
from variant_maker.server.cancel import JobCancelled
from variant_maker.server.events import VariantEvent
from variant_maker.server.fast_occupancy import FastOccupancy
from variant_maker.server.job_isolation import attempt_output_key, namespaced_input_key
from variant_maker.server.jobs import JobStore, queue_snapshot
from variant_maker.server.occupancy_journal import OccupancyJournal
from variant_maker.server.runner import SourceResult, VariantResult
from variant_maker.server.workspace import Workspace


class _HoldRunner:
    """Blocks after first start so occupancy / cancel can be observed mid-flight."""

    def __init__(self) -> None:
        self.gate = threading.Event()
        self.started = threading.Event()
        self.started_n = threading.Event()
        self._n = 0
        self._lock = threading.Lock()
        self.calls: list[tuple[str, str]] = []

    def run(self, source_path: str, *, count: int, out_dir: str, source_id: str,
            on_event: Callable[[VariantEvent], None],
            allow_creative_escalate: bool = True, quality_mode: str = "fast",
            cancel_token=None, **_kwargs) -> SourceResult:
        with self._lock:
            self._n += 1
            n = self._n
            self.calls.append((quality_mode, source_id))
        self.started.set()
        if n >= 2:
            self.started_n.set()
        os.makedirs(out_dir, exist_ok=True)
        fname = "v01.mp4"
        quality = {"vmaf": 95.0, "passed": True}
        on_event(VariantEvent(
            source_id=source_id, index=1, state="done",
            status="ok", quality=quality, filename=fname,
        ))
        open(os.path.join(out_dir, fname), "w").close()
        while not self.gate.wait(timeout=0.05):
            if cancel_token is not None and cancel_token.is_set():
                raise JobCancelled()
        mpath = os.path.join(out_dir, "manifest.json")
        open(mpath, "w").close()
        return SourceResult(
            variants=[VariantResult(
                index=1, filename=fname, status="ok", quality=quality,
                path=os.path.join(out_dir, fname),
            )],
            manifest_path=mpath,
        )


def _store(tmp_path, runner, *, workspace_id: str, occupancy, journal=None, **kw):
    return JobStore(
        Workspace(str(tmp_path / workspace_id)), runner,
        occupancy=occupancy, occupancy_journal=journal,
        workspace_id=workspace_id, **kw,
    )


def test_two_studios_take_two_fast_slots(tmp_path):
    occ = FastOccupancy(fast_slots=2, endpoint_ids=["ep-a", "ep-b"])
    runner = _HoldRunner()
    a = _store(tmp_path, runner, workspace_id="ws_a", occupancy=occ)
    b = _store(tmp_path, runner, workspace_id="ws_b", occupancy=occ)
    ja = a.create_job([("a.mp4", b"a")], count=1, quality_mode="fast")
    jb = b.create_job([("b.mp4", b"b")], count=1, quality_mode="fast")
    assert runner.started_n.wait(timeout=5)
    slots = {ja.telemetry["occupancy"]["slot"], jb.telemetry["occupancy"]["slot"]}
    assert slots == {0, 1}
    assert {ja.state, jb.state} == {"running"}
    runner.gate.set()
    assert a.wait(ja.job_id, timeout=5) and b.wait(jb.job_id, timeout=5)
    assert ja.state == "done" and jb.state == "done"


def test_same_studio_second_pack_stays_queued(tmp_path):
    occ = FastOccupancy(fast_slots=2)
    runner = _HoldRunner()
    store = _store(tmp_path, runner, workspace_id="ws_a", occupancy=occ)
    first = store.create_job([("a.mp4", b"a")], count=1, quality_mode="fast")
    assert runner.started.wait(timeout=5)
    second = store.create_job([("b.mp4", b"b")], count=1, quality_mode="fast")
    deadline = time.time() + 1.0
    while time.time() < deadline and second.state != "queued":
        time.sleep(0.02)
    assert first.state == "running"
    assert second.state == "queued"
    assert len(runner.calls) == 1
    snap = queue_snapshot(store.list())
    assert snap["running"] == 2
    assert {j["state"] for j in snap["jobs"]} == {"running", "queued"}

    store.cancel(second.job_id)
    assert store.wait(second.job_id, timeout=5)
    assert second.state == "cancelled"
    assert first.state == "running"

    runner.gate.set()
    assert store.wait(first.job_id, timeout=5)
    assert first.state == "done"


def test_cancel_queued_does_not_stop_the_other_studio(tmp_path):
    occ = FastOccupancy(fast_slots=2)
    runner = _HoldRunner()
    a = _store(tmp_path, runner, workspace_id="ws_a", occupancy=occ)
    b = _store(tmp_path, runner, workspace_id="ws_b", occupancy=occ)
    ja = a.create_job([("a.mp4", b"a")], count=1, quality_mode="fast")
    jb = b.create_job([("b.mp4", b"b")], count=1, quality_mode="fast")
    assert runner.started_n.wait(timeout=5)
    extra = a.create_job([("c.mp4", b"c")], count=1, quality_mode="fast")
    deadline = time.time() + 1.0
    while time.time() < deadline and extra.state != "queued":
        time.sleep(0.02)
    assert extra.state == "queued"
    a.cancel(extra.job_id)
    assert a.wait(extra.job_id, timeout=5)
    assert extra.state == "cancelled"
    assert ja.state == "running" and jb.state == "running"
    runner.gate.set()
    assert a.wait(ja.job_id, timeout=5) and b.wait(jb.job_id, timeout=5)


def test_occupancy_off_still_runs_fast_and_hq_together(tmp_path):
    """Default JobStore has no occupancy — shared URL Fast+HQ stay parallel."""
    runner = _HoldRunner()
    store = JobStore(Workspace(str(tmp_path)), runner)
    a = store.create_job([("va.mp4", b"aaa")], count=1, quality_mode="fast")
    b = store.create_job([("partner.mp4", b"bbb")], count=1, quality_mode="hq")
    assert runner.started_n.wait(timeout=5)
    snap = queue_snapshot(store.list())
    assert snap["running"] == 2
    assert snap["fast"] == 1 and snap["hq"] == 1
    store.cancel(a.job_id)
    assert store.wait(a.job_id, timeout=5)
    assert a.state == "cancelled"
    assert store.get(b.job_id).state == "running"
    runner.gate.set()
    assert store.wait(b.job_id, timeout=5)
    assert b.state == "done"


def test_cancel_after_done_is_already_completed(tmp_path):
    occ = FastOccupancy(fast_slots=2)
    store = _store(tmp_path, FakeRunner({}), workspace_id="ws_a", occupancy=occ)
    job = store.create_job([("a.mp4", b"x")], count=1)
    assert store.wait(job.job_id, timeout=5)
    assert job.state == "done"
    store.cancel(job.job_id)
    assert job.state == "done"


def test_new_jobs_write_namespaced_object_keys(tmp_path):
    occ = FastOccupancy(fast_slots=2)
    blob = FakeObjectStore()
    blob.put_bytes("uploads/deadbeefdead/clip.mp4", b"src")
    store = _store(
        tmp_path, FakeRunner({}), workspace_id="ws_a", occupancy=occ,
        object_store=blob,
    )
    job = store.create_job_from_object_keys(
        [("clip.mp4", "uploads/deadbeefdead/clip.mp4")], count=1,
    )
    assert store.wait(job.job_id, timeout=5)
    src = job.sources[0]
    assert src.source_object_key == namespaced_input_key(
        "ws_a", job.job_id, src.source_id, "clip.mp4",
    )
    assert blob.exists(src.source_object_key)
    assert job.attempt_id
    expected = attempt_output_key(
        "ws_a", job.job_id, job.attempt_id, src.source_id, "v01.mp4",
    )
    assert src.variants[0].object_key == expected


def test_journal_occupy_and_release_around_a_fast_job(tmp_path):
    occ = FastOccupancy(fast_slots=2)
    journal = OccupancyJournal(str(tmp_path / "fast_occupancy.json"), n_slots=2)
    store = _store(
        tmp_path, FakeRunner({}), workspace_id="ws_a", occupancy=occ,
        journal=journal,
    )
    job = store.create_job([("a.mp4", b"x")], count=1)
    assert store.wait(job.job_id, timeout=5)
    snap = journal.snapshot()
    assert snap["slots"][0]["state"] == "idle"
    assert snap["slots"][0]["job_id"] is None
    assert job.telemetry.get("occupancy", {}).get("slot") == 0


def test_tenant_hub_shares_occupancy_across_workspaces(tmp_path):
    from variant_maker.server.tenant_runtime import TenantHub

    occ = FastOccupancy(fast_slots=2)
    hub = TenantHub(str(tmp_path), FakeRunner({}), occupancy=occ)
    a = hub.bundle("ws_a").store
    b = hub.bundle("ws_b").store
    assert a._occupancy is occ is b._occupancy
    assert a._occupancy_journal is b._occupancy_journal
