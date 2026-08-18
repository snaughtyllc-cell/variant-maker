# tests/server/test_jobs.py
import os
import threading
import time
from typing import Callable

from variant_maker.server.events import VariantEvent
from variant_maker.server.jobs import JobStore
from variant_maker.server.runner import SourceResult, VariantResult
from variant_maker.server.workspace import Workspace
from tests.server.fakes import FakeRunner


def _store(tmp_path, plan=None):
    return JobStore(Workspace(str(tmp_path)), FakeRunner(plan or {}))


class _PausingRunner:
    """Emits v1 done (with uniqueness), then blocks until released — for mid-job polls."""

    def __init__(self) -> None:
        self.gate = threading.Event()
        self.v1_done = threading.Event()

    def run(self, source_path: str, *, count: int, out_dir: str, source_id: str,
            on_event: Callable[[VariantEvent], None],
            allow_creative_escalate: bool = True, quality_mode: str = "fast") -> SourceResult:
        os.makedirs(out_dir, exist_ok=True)
        variants = []
        for i in range(1, count + 1):
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
                self.gate.wait(timeout=5)
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
            allow_creative_escalate=True, quality_mode="fast"):
        on_event(VariantEvent(source_id=source_id, index=1, state="rendering"))
        raise RuntimeError("RunPod job abc ended: FAILED")


def test_runner_crash_marks_done_with_gpu_timeout_copy(tmp_path):
    store = JobStore(Workspace(str(tmp_path)), _BoomRunner())
    job = store.create_job([("a.mp4", b"x")], count=1, quality_mode="hq")
    store.wait(job.job_id, timeout=5)
    assert job.state == "done"
    assert job.error is not None
    assert "20-minute" in job.error
    assert job.sources[0].delivered == 0
