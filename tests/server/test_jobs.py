# tests/server/test_jobs.py
import json
import os
import threading
import time
from typing import Callable

from tests.server.fakes import FakeRunner
from variant_maker.server.events import VariantEvent
from variant_maker.server.jobs import (
    COPY_FAILED_MSG,
    Job,
    JobSource,
    JobStore,
    VariantInfo,
    source_copy_status,
    source_files_ready,
    variant_on_disk,
)
from variant_maker.server.runner import SourceResult, VariantResult
from variant_maker.server.workspace import Workspace


def _store(tmp_path, plan=None):
    return JobStore(Workspace(str(tmp_path)), FakeRunner(plan or {}))


class _PausingRunner:
    """Emits v1 done (with uniqueness), then blocks until released — for mid-job polls."""

    def __init__(self) -> None:
        self.gate = threading.Event()
        self.v1_done = threading.Event()

    def run(self, source_path: str, *, count: int, out_dir: str, source_id: str,
            on_event: Callable[[VariantEvent], None],
            allow_creative_escalate: bool = True, quality_mode: str = "fast",
            cancel_token=None) -> SourceResult:
        os.makedirs(out_dir, exist_ok=True)
        variants = []
        for i in range(1, count + 1):
            if cancel_token is not None and cancel_token.is_set():
                from variant_maker.server.cancel import JobCancelled
                raise JobCancelled()
            fname = f"v{i:02d}.mp4"
            quality = {"vmaf": 95.0, "bits": 27, "passed": True}
            on_event(VariantEvent(source_id=source_id, index=i, state="rendering"))
            on_event(VariantEvent(
                source_id=source_id, index=i, state="done",
                status="ok", quality=quality, filename=fname,
                uniqueness=0.42, uniqueness_status="ok",
                uniqueness_metric="ssim_bits_v1", uniqueness_target=24 / 64,
                escalated=False, preset_used="medium", strength_final=1.0,
            ))
            path = os.path.join(out_dir, fname)
            open(path, "w").close()
            variants.append(VariantResult(
                index=i, filename=fname, status="ok", quality=quality, path=path,
                uniqueness=0.42, uniqueness_status="ok",
                uniqueness_metric="ssim_bits_v1", uniqueness_target=24 / 64,
                preset_used="medium", strength_final=1.0,
            ))
            if i == 1:
                self.v1_done.set()
                while not self.gate.wait(timeout=0.05):
                    if cancel_token is not None and cancel_token.is_set():
                        from variant_maker.server.cancel import JobCancelled
                        raise JobCancelled()
        mpath = os.path.join(out_dir, "manifest.json")
        open(mpath, "w").close()
        return SourceResult(variants=variants, manifest_path=mpath)


def test_progressive_done_carries_uniqueness_before_job_finishes(tmp_path):
    runner = _PausingRunner()
    store = JobStore(Workspace(str(tmp_path)), runner)
    job = store.create_job([("a.mp4", b"x")], count=2)
    assert runner.v1_done.wait(timeout=5)
    # Mid-job: first variant must already expose uniqueness for gallery/job poll.
    deadline = time.time() + 2
    while time.time() < deadline and not job.sources[0].variants:
        time.sleep(0.01)
    assert job.sources[0].variants, "progressive done did not record a variant"
    v = job.sources[0].variants[0]
    assert v.uniqueness == 0.42
    assert v.uniqueness_status == "ok"
    assert v.uniqueness_metric == "ssim_bits_v1"
    assert v.uniqueness_target == 24 / 64
    runner.gate.set()
    store.wait(job.job_id, timeout=5)


def test_hydrate_from_disk_resumes_in_flight_job(tmp_path):
    """Studio restart must keep the job id + already-done variants, then finish the pack."""
    store = _store(tmp_path)
    job = store.create_job([("clip.mp4", b"x")], count=2)
    store.wait(job.job_id, timeout=5)
    meta = os.path.join(str(tmp_path), "jobs", job.job_id, "job.json")
    with open(meta, encoding="utf-8") as f:
        data = json.load(f)
    assert data["state"] == "done"
    data["state"] = "running"
    data["sources"][0]["variants"] = data["sources"][0]["variants"][:1]
    with open(meta, "w", encoding="utf-8") as f:
        json.dump(data, f)

    store2 = JobStore(Workspace(str(tmp_path)), FakeRunner({}))
    assert store2.hydrate_from_disk() == 1
    restored = store2.get(job.job_id)
    assert restored is not None
    assert restored.sources[0].variants[0].index == 1
    assert store2.wait(job.job_id, timeout=5)
    assert restored.state == "done"
    assert len(restored.sources[0].variants) == 2


def test_create_job_runs_in_background_and_completes(tmp_path):
    store = _store(tmp_path)
    job = store.create_job([("a.mp4", b"x"), ("b.mp4", b"y")], count=3)
    assert job.state in ("running", "done")
    store.wait(job.job_id, timeout=5)
    done = store.get(job.job_id)
    assert done.state == "done"
    assert len(done.sources) == 2
    for s in done.sources:
        assert len(s.variants) == 3
        assert s.requested == 3


def test_delivered_and_shortfall_count_only_ok(tmp_path):
    # variant 2 is best_effort -> delivered 2 of 3, shortfall 1
    store = _store(tmp_path, plan={2: "best_effort"})
    job = store.create_job([("a.mp4", b"x")], count=3)
    store.wait(job.job_id, timeout=5)
    src = store.get(job.job_id).sources[0]
    assert src.delivered == 2
    assert src.shortfall == 1


def test_events_recorded_per_job(tmp_path):
    store = _store(tmp_path)
    job = store.create_job([("a.mp4", b"x")], count=2)
    store.wait(job.job_id, timeout=5)
    states = [e.state for e in store.get(job.job_id).events]
    assert states.count("done") == 2
    assert "rendering" in states


def test_gallery_and_diagnostics_split_by_status(tmp_path):
    store = _store(tmp_path, plan={2: "best_effort"})
    job = store.create_job([("a.mp4", b"x")], count=3)
    store.wait(job.job_id, timeout=5)

    gallery = store.gallery()
    assert len(gallery) == 1
    ok_in_gallery = [v for v in gallery[0].variants if v.status == "ok"]
    assert len(ok_in_gallery) == 2

    diag = store.diagnostics()
    assert len(diag) == 1
    assert diag[0].status == "best_effort"


def test_find_variant_and_source_file(tmp_path):
    store = _store(tmp_path)
    job = store.create_job([("a.mp4", b"orig-bytes")], count=2)
    store.wait(job.job_id, timeout=5)
    src = store.get(job.job_id).sources[0]
    vpath = store.find_variant(src.source_id, src.variants[0].filename)
    assert vpath and vpath.endswith(".mp4")
    spath = store.source_file(src.source_id)
    with open(spath, "rb") as f:
        assert f.read() == b"orig-bytes"


def test_find_variant_rejects_path_traversal(tmp_path):
    store = _store(tmp_path)
    job = store.create_job([("a.mp4", b"x")], count=1)
    store.wait(job.job_id, timeout=5)
    sid = store.get(job.job_id).sources[0].source_id
    assert store.find_variant(sid, "../../etc/passwd") is None
    assert store.find_variant(sid, "sub/v01.mp4") is None
    assert store.find_variant(sid, "..") is None
    assert store.find_variant(sid, "") is None


def test_regenerate_appends_variants(tmp_path):
    store = _store(tmp_path)
    job = store.create_job([("a.mp4", b"x")], count=2)
    store.wait(job.job_id, timeout=5)
    src = store.get(job.job_id).sources[0]
    result = store.regenerate(src.source_id, 2)
    assert result is not None
    assert result is src
    assert len(src.variants) == 4
    assert [v.index for v in src.variants] == [1, 2, 3, 4]


def test_create_job_passes_quality_mode_hq_to_runner(tmp_path):
    runner = FakeRunner()
    store = JobStore(Workspace(str(tmp_path)), runner)
    job = store.create_job([("a.mp4", b"x")], count=1, quality_mode="hq")
    store.wait(job.job_id, timeout=5)
    assert runner.last_quality_mode == "hq"
    assert job.quality_mode == "hq"


def test_regenerate_keeps_job_quality_mode(tmp_path):
    runner = FakeRunner()
    store = JobStore(Workspace(str(tmp_path)), runner)
    job = store.create_job([("a.mp4", b"x")], count=1, quality_mode="hq")
    store.wait(job.job_id, timeout=5)
    src = store.get(job.job_id).sources[0]
    store.regenerate(src.source_id, 1)
    assert runner.last_quality_mode == "hq"


class _BoomRunner:
    def run(self, source_path, *, count, out_dir, source_id, on_event,
            allow_creative_escalate=True, quality_mode="fast", cancel_token=None):
        on_event(VariantEvent(source_id=source_id, index=1, state="rendering"))
        raise RuntimeError("RunPod job abc ended: FAILED")


def test_cancel_stops_after_first_variant(tmp_path):
    runner = _PausingRunner()
    store = JobStore(Workspace(str(tmp_path)), runner)
    job = store.create_job([("a.mp4", b"x")], count=2)
    assert runner.v1_done.wait(timeout=5)
    out = store.cancel(job.job_id)
    assert out is job
    store.wait(job.job_id, timeout=5)
    assert job.state == "cancelled"
    assert "Cancelled" in (job.error or "")
    assert len(job.sources[0].variants) == 1


def test_cancel_unknown_job_is_none(tmp_path):
    store = _store(tmp_path)
    assert store.cancel("nope") is None


def test_runner_crash_marks_done_with_gpu_timeout_copy(tmp_path):
    store = JobStore(Workspace(str(tmp_path)), _BoomRunner())
    job = store.create_job([("a.mp4", b"x")], count=1, quality_mode="hq")
    store.wait(job.job_id, timeout=5)
    assert job.state == "done"
    assert job.error is not None
    assert "20 minutes" in job.error
    assert "New run" in job.error
    assert job.sources[0].delivered == 0


def test_copy_status_is_disk_only(tmp_path):
    """Metadata can say ok while the mp4 is gone — Gallery must not trust delivered."""
    ws = Workspace(str(tmp_path))
    source = JobSource(
        source_id="src1", filename="a.mp4", requested=2,
        variants=[
            VariantInfo(source_id="src1", index=1, filename="v01.mp4",
                        status="ok", quality={"vmaf": 95.0}),
            VariantInfo(source_id="src1", index=2, filename="v02.mp4",
                        status="ok", quality={"vmaf": 95.0}),
        ],
    )
    assert source.delivered == 2
    assert source_files_ready(source, ws, "job1") == 0
    assert source_copy_status(source, ws, "job1", "done") == "missing"
    assert source_copy_status(source, ws, "job1", "running") == "copying"

    out = ws.source_out_dir("job1", "src1")
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "v01.mp4"), "w").close()
    open(os.path.join(out, "v02.mp4"), "w").close()
    assert variant_on_disk(ws, "job1", "src1", "v01.mp4")
    assert source_files_ready(source, ws, "job1") == 2
    assert source_copy_status(source, ws, "job1", "done") == "ok"


class _MetaOnlyRunner:
    """GPU-style: events + result metadata, no files written (copy never landed)."""

    def run(self, source_path, *, count, out_dir, source_id, on_event,
            allow_creative_escalate=True, quality_mode="fast", cancel_token=None):
        os.makedirs(out_dir, exist_ok=True)
        variants = []
        for i in range(1, count + 1):
            fname = f"v{i:02d}.mp4"
            quality = {"vmaf": 95.0, "passed": True}
            on_event(VariantEvent(
                source_id=source_id, index=i, state="done",
                status="ok", quality=quality, filename=fname,
            ))
            variants.append(VariantResult(
                index=i, filename=fname, status="ok", quality=quality,
                path=os.path.join(out_dir, fname),
            ))
        return SourceResult(variants=variants, manifest_path=os.path.join(out_dir, "manifest.json"))

    def fetch_outputs(self, source_id, out_dir, filenames):
        return 0


def test_job_errors_when_ok_metadata_has_no_files(tmp_path):
    store = JobStore(Workspace(str(tmp_path)), _MetaOnlyRunner())
    job = store.create_job([("a.mp4", b"x")], count=2)
    store.wait(job.job_id, timeout=5)
    assert job.state == "done"
    assert job.sources[0].delivered == 2
    assert job.error == COPY_FAILED_MSG
    assert source_files_ready(job.sources[0], store._ws, job.job_id) == 0


def test_retry_copy_pulls_missing_and_clears_copy_error(tmp_path):
    from tests.server.fakes import FakeObjectStore, FakeRunPodClient
    from variant_maker.server.runpod_runner import RunPodServerlessRunner

    blobstore = FakeObjectStore()
    ws = Workspace(str(tmp_path))
    runner = RunPodServerlessRunner(blobstore, FakeRunPodClient([]))
    store = JobStore(ws, runner)
    job_id, source_id = "jobretry01", "srcretry01"
    out_dir = ws.source_out_dir(job_id, source_id)
    os.makedirs(out_dir, exist_ok=True)
    staged = tmp_path / "staged.mp4"
    staged.write_bytes(b"RETRY-COPY-BYTES")
    blobstore.put(f"outputs/{source_id}/v01.mp4", str(staged))

    job = Job(
        job_id=job_id, count=1, created_utc="2026-08-18T00:00:00Z",
        sources=[JobSource(
            source_id=source_id, filename="clip.mp4", requested=1,
            variants=[VariantInfo(
                source_id=source_id, index=1, filename="v01.mp4", status="ok",
                quality={"vmaf": 99.0},
            )],
        )],
        state="done", error=COPY_FAILED_MSG,
    )
    store._install_hydrated_job(job)
    # hydrate already pulls — wipe the copy so retry-copy is the path under test
    os.remove(os.path.join(out_dir, "v01.mp4"))
    assert source_files_ready(job.sources[0], ws, job_id) == 0

    out = store.retry_copy(source_id)
    assert out is job.sources[0]
    assert source_files_ready(job.sources[0], ws, job_id) == 1
    assert job.error is None
    assert store.retry_copy("nope") is None


def test_delete_source_drops_pack_from_gallery_and_disk(tmp_path):
    store = _store(tmp_path)
    job = store.create_job([("a.mp4", b"x")], count=2)
    store.wait(job.job_id, timeout=5)
    sid = job.sources[0].source_id
    job_dir = os.path.join(str(tmp_path), "jobs", job.job_id)
    assert os.path.isdir(job_dir)
    assert store.delete_source(sid) is True
    assert store.gallery() == []
    assert store.get(job.job_id) is None
    assert not os.path.isdir(job_dir)
    assert store.delete_source(sid) is False
    store2 = JobStore(Workspace(str(tmp_path)), FakeRunner({}))
    assert store2.hydrate_from_disk() == 0


def test_delete_one_source_keeps_sibling(tmp_path):
    store = _store(tmp_path)
    job = store.create_job([("a.mp4", b"x"), ("b.mp4", b"y")], count=1)
    store.wait(job.job_id, timeout=5)
    first, second = job.sources[0].source_id, job.sources[1].source_id
    assert store.delete_source(first) is True
    assert [s.source_id for s in store.gallery()] == [second]
    assert store.get(job.job_id) is not None
    assert os.path.isfile(os.path.join(str(tmp_path), "jobs", job.job_id, "job.json"))


def test_delete_running_source_cancels_and_does_not_resurrect(tmp_path):
    runner = _PausingRunner()
    store = JobStore(Workspace(str(tmp_path)), runner)
    job = store.create_job([("a.mp4", b"x")], count=2)
    assert runner.v1_done.wait(timeout=5)
    sid = job.sources[0].source_id
    job_id = job.job_id
    assert store.delete_source(sid) is True
    store.wait(job_id, timeout=5)
    time.sleep(0.15)
    assert store.get(job_id) is None
    assert store.gallery() == []
    assert not os.path.isdir(os.path.join(str(tmp_path), "jobs", job_id))


class _HoldRunner:
    """Starts two sources in parallel and holds until released — isolation + queue."""

    def __init__(self) -> None:
        self.started: list[tuple[str, str]] = []
        self.gate = threading.Event()
        self._lock = threading.Lock()
        self.started_n = threading.Event()

    def run(self, source_path: str, *, count: int, out_dir: str, source_id: str,
            on_event: Callable[[VariantEvent], None],
            allow_creative_escalate: bool = True, quality_mode: str = "fast",
            cancel_token=None) -> SourceResult:
        os.makedirs(out_dir, exist_ok=True)
        with self._lock:
            self.started.append((source_path, out_dir))
            if len(self.started) >= 2:
                self.started_n.set()
        fname = "v01.mp4"
        quality = {"vmaf": 95.0, "passed": True}
        on_event(VariantEvent(
            source_id=source_id, index=1, state="done",
            status="ok", quality=quality, filename=fname,
        ))
        open(os.path.join(out_dir, fname), "w").close()
        while not self.gate.wait(timeout=0.05):
            if cancel_token is not None and cancel_token.is_set():
                from variant_maker.server.cancel import JobCancelled
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


def test_two_jobs_use_separate_folders_and_cancel_is_per_job(tmp_path):
    """Shared Studio URL: two Generates must not mix files or cancel each other."""
    from variant_maker.server.jobs import queue_snapshot

    runner = _HoldRunner()
    store = JobStore(Workspace(str(tmp_path)), runner)
    a = store.create_job([("va.mp4", b"aaa")], count=1, quality_mode="fast")
    b = store.create_job([("partner.mp4", b"bbb")], count=1, quality_mode="hq")
    assert runner.started_n.wait(timeout=5)
    paths_a = store._ws.source_in_path(a.job_id, a.sources[0].source_id, "va.mp4")
    paths_b = store._ws.source_in_path(b.job_id, b.sources[0].source_id, "partner.mp4")
    assert os.path.isfile(paths_a) and os.path.isfile(paths_b)
    assert os.path.dirname(os.path.dirname(paths_a)) != os.path.dirname(os.path.dirname(paths_b))
    with open(paths_a, "rb") as f:
        assert f.read() == b"aaa"
    with open(paths_b, "rb") as f:
        assert f.read() == b"bbb"
    out_dirs = {out for _, out in runner.started}
    assert len(out_dirs) == 2

    snap = queue_snapshot(store.list())
    assert snap["running"] == 2
    assert snap["fast"] == 1 and snap["hq"] == 1
    assert [j["position"] for j in snap["jobs"]] == [1, 2]
    names = {tuple(j["filenames"]) for j in snap["jobs"]}
    assert names == {("va.mp4",), ("partner.mp4",)}
    assert all("file_url" not in j for j in snap["jobs"])

    store.cancel(a.job_id)
    assert store.wait(a.job_id, timeout=5)
    assert a.state == "cancelled"
    assert store.get(b.job_id).state == "running"
    snap = queue_snapshot(store.list())
    assert snap["running"] == 1
    assert snap["jobs"][0]["job_id"] == b.job_id

    runner.gate.set()
    assert store.wait(b.job_id, timeout=5)
    assert b.state == "done"
    assert queue_snapshot(store.list())["running"] == 0


def test_set_post_url_survives_hydrate(tmp_path):
    store = _store(tmp_path)
    job = store.create_job([("a.mp4", b"x")], count=1)
    store.wait(job.job_id, timeout=5)
    src = store.get(job.job_id).sources[0]
    url = "https://www.instagram.com/reel/Hydrate1/"
    updated = store.set_post_url(src.source_id, src.variants[0].index, url)
    assert updated is not None
    assert updated.post_url == url

    store2 = JobStore(Workspace(str(tmp_path)), FakeRunner({}))
    assert store2.hydrate_from_disk() == 1
    restored = store2.get(job.job_id).sources[0].variants[0]
    assert restored.post_url == url
    assert restored.platform_result is None


class _OccupancyFake(FakeRunner):
    """Records which Fast CPU was used. Optional hold on the first run() keeps the lease."""

    def __init__(self, *, hold_first: bool = False) -> None:
        super().__init__({})
        self.calls: list[dict] = []
        self.started = threading.Event()
        self.gate = threading.Event()
        self._seen = 0
        if not hold_first:
            self.gate.set()

    def run(self, source_path: str, *, count: int, out_dir: str, source_id: str,
            on_event: Callable[[VariantEvent], None],
            allow_creative_escalate: bool = True, quality_mode: str = "fast",
            cancel_token=None) -> SourceResult:
        self._seen += 1
        self.calls.append({
            "count": count, "quality_mode": quality_mode, "source_id": source_id,
        })
        if self._seen == 1 and not self.gate.is_set():
            self.started.set()
            if not self.gate.wait(timeout=5):
                raise TimeoutError("occupancy hold")
        else:
            self.started.set()
        return super().run(
            source_path, count=count, out_dir=out_dir, source_id=source_id,
            on_event=on_event, allow_creative_escalate=allow_creative_escalate,
            quality_mode=quality_mode, cancel_token=cancel_token,
        )


def _occupancy_pair(tmp_path, *, hold_primary: bool = False, hold_gpu: bool = False):
    from variant_maker.server.runner import RoutingRunner

    local, gpu = _OccupancyFake(), _OccupancyFake(hold_first=hold_gpu)
    fast, fast2 = _OccupancyFake(hold_first=hold_primary), _OccupancyFake()
    router = RoutingRunner(local, gpu, fast_remotes=[fast, fast2], max_local_fast=3)
    store_a = JobStore(Workspace(str(tmp_path / "jeff")), router, workspace_id="ws_jeff")
    store_b = JobStore(Workspace(str(tmp_path / "partner")), router, workspace_id="ws_partner")
    return store_a, store_b, local, gpu, fast, fast2


def test_jobstore_second_workspace_fast_uses_overflow_cpu(tmp_path):
    """Workspace A holding Fast → workspace B boots the overflow CPU. Pack stays sticky."""
    store_a, store_b, local, gpu, fast, fast2 = _occupancy_pair(tmp_path, hold_primary=True)
    job_a = store_a.create_job([("a1.mp4", b"x"), ("a2.mp4", b"y")], count=8)
    assert fast.started.wait(timeout=5)
    job_b = store_b.create_job([("b1.mp4", b"z")], count=8)
    assert store_b.wait(job_b.job_id, timeout=5)
    assert [c["count"] for c in fast2.calls] == [8]
    assert not gpu.calls and not local.calls
    fast.gate.set()
    assert store_a.wait(job_a.job_id, timeout=5)
    assert [c["count"] for c in fast.calls] == [8, 8]
    assert len(fast2.calls) == 1


def test_jobstore_same_workspace_second_job_stays_on_primary(tmp_path):
    store_a, _store_b, _local, gpu, fast, fast2 = _occupancy_pair(tmp_path, hold_primary=True)
    job1 = store_a.create_job([("a.mp4", b"x")], count=8)
    assert fast.started.wait(timeout=5)
    job2 = store_a.create_job([("a2.mp4", b"y")], count=8)
    assert store_a.wait(job2.job_id, timeout=5)
    assert all(c["count"] == 8 for c in fast.calls)
    assert len(fast.calls) >= 2
    assert not fast2.calls and not gpu.calls
    fast.gate.set()
    assert store_a.wait(job1.job_id, timeout=5)


def test_jobstore_one_studio_stays_on_primary_fast(tmp_path):
    store_a, _store_b, _local, gpu, fast, fast2 = _occupancy_pair(tmp_path)
    job = store_a.create_job([("a.mp4", b"x")], count=8)
    assert store_a.wait(job.job_id, timeout=5)
    assert [c["count"] for c in fast.calls] == [8]
    assert not fast2.calls and not gpu.calls


def test_jobstore_hq_does_not_take_fast_overflow_slot(tmp_path):
    store_a, store_b, _local, gpu, fast, fast2 = _occupancy_pair(tmp_path, hold_gpu=True)
    job_hq = store_a.create_job([("hq.mp4", b"x")], count=1, quality_mode="hq")
    assert gpu.started.wait(timeout=5)
    job_fast = store_b.create_job([("fast.mp4", b"y")], count=8)
    assert store_b.wait(job_fast.job_id, timeout=5)
    assert [c["count"] for c in fast.calls] == [8]
    assert not fast2.calls
    gpu.gate.set()
    assert store_a.wait(job_hq.job_id, timeout=5)


def test_jobstore_regenerate_uses_overflow_when_other_workspace_busy(tmp_path):
    store_a, store_b, _local, gpu, fast, fast2 = _occupancy_pair(tmp_path, hold_primary=True)
    job_a = store_a.create_job([("a.mp4", b"x")], count=8)
    assert fast.started.wait(timeout=5)
    job_b = store_b.create_job([("b.mp4", b"y")], count=8)
    assert store_b.wait(job_b.job_id, timeout=5)
    overflow_n = len(fast2.calls)
    src = job_b.sources[0]
    store_b.regenerate(src.source_id, 2)
    assert len(fast2.calls) == overflow_n + 1
    assert fast2.calls[-1]["count"] == 2
    assert not gpu.calls
    fast.gate.set()
    assert store_a.wait(job_a.job_id, timeout=5)
