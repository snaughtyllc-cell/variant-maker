from datetime import UTC, datetime, timedelta

from variant_maker.server.usage import (
    backfill_jobs,
    record_job,
    usage_path,
    usage_windows,
)
from variant_maker.server.workspace import Workspace


class _Src:
    def __init__(self, delivered: int) -> None:
        self.delivered = delivered


class _Job:
    def __init__(self, **kw) -> None:
        self.job_id = kw.get("job_id", "j1")
        self.state = kw.get("state", "done")
        self.count = kw.get("count", 3)
        self.created_utc = kw.get("created_utc", "2026-08-30T12:00:00Z")
        self.sources = kw.get("sources", [_Src(3), _Src(3)])


def test_record_job_counts_sources_and_copies(tmp_path):
    ws = Workspace(str(tmp_path))
    job = _Job()
    assert record_job(ws, job) is True
    assert record_job(ws, job) is False
    windows = usage_windows(ws, now=datetime(2026, 8, 30, 18, tzinfo=UTC))
    assert windows["week"].sources == 2
    assert windows["week"].copies == 6
    assert windows["month"].packs == 1
    assert windows["all"].copies == 6
    assert usage_path(ws).endswith("usage.jsonl")


def test_zero_delivered_job_is_not_recorded(tmp_path):
    ws = Workspace(str(tmp_path))
    assert record_job(ws, _Job(sources=[_Src(0)], count=3)) is False
    assert usage_windows(ws)["all"].packs == 0


def test_finished_job_writes_ledger(tmp_path):
    from tests.server.fakes import FakeRunner
    from variant_maker.server.jobs import JobStore

    ws = Workspace(str(tmp_path))
    store = JobStore(ws, FakeRunner({}), gallery_keep_jobs=0, gallery_keep_hours=0)
    job = store.create_job([("a.mp4", b"x")], count=2)
    assert store.wait(job.job_id, timeout=5)
    windows = usage_windows(ws)
    assert windows["all"].sources == 1
    assert windows["all"].copies == 2
    assert windows["week"].packs == 1



def test_backfill_and_month_window(tmp_path):
    ws = Workspace(str(tmp_path))
    now = datetime(2026, 8, 30, 12, tzinfo=UTC)
    old = _Job(
        job_id="old",
        created_utc=(now - timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        sources=[_Src(2)],
        count=2,
    )
    fresh = _Job(
        job_id="new",
        created_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        sources=[_Src(4)],
        count=4,
    )
    assert backfill_jobs(ws, [old, fresh]) == 2
    windows = usage_windows(ws, now=now)
    assert windows["week"].sources == 1
    assert windows["week"].copies == 4
    assert windows["month"].sources == 2
    assert windows["month"].copies == 6
    assert windows["all"].packs == 2
