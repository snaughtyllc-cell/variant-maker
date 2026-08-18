import time
from pathlib import Path

import pytest

from farm_fakes import FakeDrive
from tests.server.fakes import FakeRunner
from variant_maker.server.drive_exports import (
    ExportError,
    ExportRunner,
    ExportStore,
    VariantRef,
    build_export_files,
)
from variant_maker.server.jobs import Job, JobSource, JobStore, VariantInfo
from variant_maker.server.workspace import Workspace


def _store_with_ok(tmp_path):
    ws = Workspace(str(tmp_path))
    store = JobStore(ws, FakeRunner({}))
    # manually seed a done job with one ok variant on disk
    job = Job(job_id="j1", count=1, created_utc="2026-01-01T00:00:00Z", state="done")
    src = JobSource(source_id="s1", filename="a.mp4", requested=1)
    out = ws.source_out_dir("j1", "s1")
    path = Path(out) / "v01.mp4"
    path.write_bytes(b"video-bytes")
    src.variants.append(VariantInfo(
        source_id="s1", index=1, filename="v01.mp4", status="ok", quality={"vmaf": 95},
    ))
    job.sources.append(src)
    store._jobs["j1"] = job
    store._source_index["s1"] = ("j1", src)
    return store, ws


def test_build_export_files_filters_non_ok(tmp_path):
    store, ws = _store_with_ok(tmp_path)
    job = store.get("j1")
    job.sources[0].variants.append(VariantInfo(
        source_id="s1", index=2, filename="v02.mp4", status="best_effort", quality={},
    ))
    files = build_export_files(store, [VariantRef("s1", 1), VariantRef("s1", 2)])
    assert len(files) == 1 and files[0].filename == "v01.mp4"


def test_build_export_files_empty_raises(tmp_path):
    store, _ = _store_with_ok(tmp_path)
    with pytest.raises(ExportError, match="No ok videos"):
        build_export_files(store, [VariantRef("s1", 2)])  # missing index


def test_runner_uploads_and_suffixes_collision(tmp_path):
    store, ws = _store_with_ok(tmp_path)
    drive = FakeDrive()
    folder = drive.make_folder("out")
    # existing collision
    p = tmp_path / "pre.mp4"
    p.write_bytes(b"old")
    drive.upload(str(p), folder, name="v01.mp4")
    exports = ExportStore(ws.exports_dir())
    files = build_export_files(store, [VariantRef("s1", 1)])
    job = exports.create(destination_id="dst_x", folder_id=folder, files=files)
    ExportRunner(drive, exports).start(job)
    for _ in range(50):
        job = exports.get(job.export_id)
        if job.state in ("succeeded", "partial", "failed"):
            break
        time.sleep(0.05)
    assert job.state == "succeeded"
    names = {f.name for f in drive.list_files(folder)}
    assert "v01 (1).mp4" in names
    assert job.files[0].drive_file_id


def test_partial_failure_and_retry(tmp_path):
    store, ws = _store_with_ok(tmp_path)
    # add second ok file
    out = ws.source_out_dir("j1", "s1")
    Path(out, "v02.mp4").write_bytes(b"v2")
    store.get("j1").sources[0].variants.append(VariantInfo(
        source_id="s1", index=2, filename="v02.mp4", status="ok", quality={"vmaf": 90},
    ))
    drive = FakeDrive()
    folder = drive.make_folder("out")
    exports = ExportStore(ws.exports_dir())
    files = build_export_files(store, [VariantRef("s1", 1), VariantRef("s1", 2)])
    job = exports.create(destination_id="dst_x", folder_id=folder, files=files)

    class FlakyDrive:
        def __init__(self, inner):
            self._inner = inner
            self._fail_once = {"v01.mp4"}

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def upload(self, local_path, parent_id, name=None):
            n = name or Path(local_path).name
            if n in self._fail_once:
                self._fail_once.discard(n)
                raise RuntimeError("quota exceeded")
            return self._inner.upload(local_path, parent_id, name)

    runner = ExportRunner(FlakyDrive(drive), exports)
    runner.start(job)
    for _ in range(50):
        job = exports.get(job.export_id)
        if job.state in ("succeeded", "partial", "failed"):
            break
        time.sleep(0.05)
    assert job.state == "partial"
    assert sum(1 for f in job.files if f.status == "failed") == 1
    job = runner.retry_failed(job.export_id)
    for _ in range(50):
        job = exports.get(job.export_id)
        if job.state == "succeeded":
            break
        time.sleep(0.05)
    assert job.state == "succeeded"
    assert all(f.status == "succeeded" for f in job.files)
