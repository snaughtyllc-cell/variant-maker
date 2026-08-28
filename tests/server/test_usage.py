"""Weekly usage ledger — survives gallery prune, last 7 days, no double-count."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tests.server.fakes import FakeRunner
from variant_maker.server.jobs import Job, JobSource, JobStore, VariantInfo
from variant_maker.server.usage import USAGE_FILENAME, record_job, week_rollup
from variant_maker.server.workspace import Workspace


def _job(
    tmp_path,
    *,
    job_id="j1",
    quality_mode="fast",
    prep_mode="none",
    delivered=2,
    requested=2,
    prep_status=None,
    created_utc=None,
) -> tuple[Workspace, Job]:
    ws = Workspace(str(tmp_path))
    variants = [
        VariantInfo(
            source_id="s1", index=i, filename=f"v{i:02d}.mp4",
            status="ok", quality={"vmaf": 95.0},
        )
        for i in range(1, delivered + 1)
    ]
    source = JobSource(
        source_id="s1", filename="a.mp4", requested=requested,
        variants=variants, prep_status=prep_status,
    )
    job = Job(
        job_id=job_id,
        count=requested,
        created_utc=created_utc or "2026-08-28T12:00:00Z",
        sources=[source],
        state="done",
        quality_mode=quality_mode,
        prep_mode=prep_mode,
    )
    return ws, job


def test_week_rollup_empty_is_zeros(tmp_path):
    ws = Workspace(str(tmp_path))
    r = week_rollup(ws)
    assert r.fast_copies == 0
    assert r.hq_preps == 0
    assert r.packs == 0


def test_record_fast_job_counts_delivered_copies(tmp_path):
    ws, job = _job(tmp_path, delivered=3, requested=3)
    record_job(ws, job)
    r = week_rollup(ws)
    assert r.fast_copies == 3
    assert r.hq_preps == 0
    assert r.packs == 1
    assert (tmp_path / USAGE_FILENAME).is_file()


def test_record_hq_prep_then_fast_splits_week_columns(tmp_path):
    ws, job = _job(
        tmp_path, prep_mode="hq", prep_status="done", delivered=4, requested=4,
    )
    record_job(ws, job)
    r = week_rollup(ws)
    assert r.fast_copies == 4
    assert r.hq_preps == 1
    assert r.packs == 1


def test_standalone_hq_pack_counts_as_week_hq(tmp_path):
    ws, job = _job(tmp_path, quality_mode="hq", delivered=1, requested=1)
    record_job(ws, job)
    r = week_rollup(ws)
    assert r.fast_copies == 0
    assert r.hq_preps == 1
    assert r.packs == 1


def test_record_job_is_idempotent_on_job_id(tmp_path):
    ws, job = _job(tmp_path, delivered=2)
    record_job(ws, job)
    record_job(ws, job)
    r = week_rollup(ws)
    assert r.fast_copies == 2
    assert r.packs == 1


def test_week_rollup_ignores_lines_older_than_7_days(tmp_path):
    ws, old = _job(tmp_path, job_id="old", delivered=9)
    record_job(ws, old, now=datetime(2026, 8, 1, tzinfo=UTC))
    ws, fresh = _job(tmp_path, job_id="new", delivered=2)
    record_job(ws, fresh, now=datetime(2026, 8, 28, 12, tzinfo=UTC))
    r = week_rollup(ws, now=datetime(2026, 8, 28, 12, tzinfo=UTC))
    assert r.fast_copies == 2
    assert r.packs == 1


def test_cancelled_job_is_not_recorded(tmp_path):
    ws, job = _job(tmp_path, delivered=1)
    job.state = "cancelled"
    record_job(ws, job)
    assert week_rollup(ws).packs == 0


def test_usage_survives_job_delete(tmp_path):
    runner = FakeRunner()
    store = JobStore(Workspace(str(tmp_path)), runner)
    job = store.create_job([("a.mp4", b"x")], count=2)
    store.wait(job.job_id, timeout=5)
    assert week_rollup(store._ws).fast_copies == 2
    store.delete_job(job.job_id)
    assert week_rollup(store._ws).fast_copies == 2
    assert not (tmp_path / "jobs" / job.job_id).exists()


def test_hq_prep_failure_does_not_count_a_prep(tmp_path):
    ws, job = _job(
        tmp_path, prep_mode="hq", prep_status="failed", delivered=0, requested=4,
    )
    record_job(ws, job)
    r = week_rollup(ws)
    assert r.hq_preps == 0
    assert r.fast_copies == 0
    assert r.packs == 1


def test_week_window_is_seven_days_inclusive(tmp_path):
    now = datetime(2026, 8, 28, 12, tzinfo=UTC)
    ws, edge = _job(tmp_path, job_id="edge", delivered=1)
    record_job(ws, edge, now=now - timedelta(days=7) + timedelta(seconds=1))
    r = week_rollup(ws, now=now)
    assert r.fast_copies == 1
