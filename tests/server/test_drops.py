"""Drops board: Drive-sent packs joined to Gallery platform_result.

Unlabeled / passed / unknown = pass. flagged / duplicate_reject = miss.
Identity is job_id + {source_id}:{index}, never the caption filename.
"""
from pathlib import Path

from farm_fakes import FakeDrive
from fastapi.testclient import TestClient

from tests.server.fakes import FakeRunner
from variant_maker.server.app import create_app
from variant_maker.server.destinations import DestinationStore
from variant_maker.server.drive_exports import ExportFile, ExportJob, ExportStore
from variant_maker.server.drops import build_drop_packs, drop_outcome, variant_id
from variant_maker.server.jobs import Job, JobSource, JobStore, VariantInfo
from variant_maker.server.workspace import Workspace


def _ok_file(*, source_id="s1", index=1, status="succeeded", drive_file_id="drv_1"):
    return ExportFile(
        source_id=source_id, index=index, filename="ignored-caption.mp4",
        local_path="/tmp/v.mp4", status=status, drive_file_id=drive_file_id,
    )


def test_drop_outcome_unlabeled_is_pass():
    assert drop_outcome(None) == "pass"
    assert drop_outcome("") == "pass"
    assert drop_outcome("passed") == "pass"
    assert drop_outcome("unknown") == "pass"


def test_drop_outcome_flagged_and_duplicate_are_miss():
    assert drop_outcome("flagged") == "miss"
    assert drop_outcome("duplicate_reject") == "miss"


def test_variant_id_is_source_and_index_not_caption():
    assert variant_id("src_abc", 3) == "src_abc:3"


def test_export_store_list_newest_first(tmp_path):
    ws = Workspace(str(tmp_path))
    exports = ExportStore(ws.exports_dir())
    older = ExportJob(
        export_id="exp_old", destination_id="dst_a", folder_id="fld",
        state="succeeded", created_utc="2026-08-01T00:00:00Z",
        files=[_ok_file()],
    )
    newer = ExportJob(
        export_id="exp_new", destination_id="dst_a", folder_id="fld",
        state="succeeded", created_utc="2026-08-20T12:00:00Z",
        files=[_ok_file(index=2, drive_file_id="drv_2")],
    )
    exports.save(older)
    exports.save(newer)
    listed = exports.list()
    assert [j.export_id for j in listed] == ["exp_new", "exp_old"]


def test_export_store_list_skips_corrupt_and_temp(tmp_path):
    ws = Workspace(str(tmp_path))
    exports = ExportStore(ws.exports_dir())
    job = ExportJob(
        export_id="exp_ok", destination_id="dst_a", folder_id="fld",
        state="succeeded", created_utc="2026-08-20T00:00:00Z",
        files=[_ok_file()],
    )
    exports.save(job)
    Path(ws.exports_dir(), "exp_bad.json").write_text("{not-json", encoding="utf-8")
    Path(ws.exports_dir(), ".exp_ok-tmp.json").write_text("{}", encoding="utf-8")
    listed = exports.list()
    assert [j.export_id for j in listed] == ["exp_ok"]


def _seed_job(store, *, platform_result=None):
    job = Job(job_id="j1", count=1, created_utc="2026-08-20T00:00:00Z", state="done")
    src = JobSource(source_id="s1", filename="a.mp4", requested=1)
    src.variants.append(VariantInfo(
        source_id="s1", index=1, filename="v01.mp4", status="ok", quality={},
        platform_result=platform_result,
    ))
    job.sources.append(src)
    store._jobs["j1"] = job
    store._source_index["s1"] = ("j1", src)
    return job


def test_build_drop_packs_joins_destination_and_skips_unsent(tmp_path):
    ws = Workspace(str(tmp_path))
    store = JobStore(ws, FakeRunner({}))
    _seed_job(store, platform_result="flagged")
    dests = DestinationStore(ws.destinations_path())
    dest = dests.create(name="LOGAN REPURPOSE 1", folder_id="fld")
    exports = [
        ExportJob(
            export_id="exp_sent", destination_id=dest.id, folder_id="fld",
            state="succeeded", created_utc="2026-08-21T10:00:00Z",
            files=[_ok_file()],
        ),
        ExportJob(
            export_id="exp_pending", destination_id=dest.id, folder_id="fld",
            state="running", created_utc="2026-08-21T11:00:00Z",
            files=[_ok_file(status="pending", drive_file_id=None)],
        ),
    ]
    packs = build_drop_packs(exports, dests, store)
    assert len(packs) == 1
    pack = packs[0]
    assert pack.destination_name == "LOGAN REPURPOSE 1"
    assert pack.count == 1
    assert pack.outcome == "miss"
    assert pack.miss_labels == ("flagged",)
    assert pack.files[0].variant_id == "s1:1"
    assert pack.files[0].job_id == "j1"
    assert pack.files[0].drive_file_id == "drv_1"
    assert not hasattr(pack.files[0], "filename")


def test_get_drive_exports_lists_sent_packs(tmp_path):
    ws = Workspace(str(tmp_path))
    store = JobStore(ws, FakeRunner({}))
    client = TestClient(create_app(store, drive=FakeDrive(), sa_json_path=""))
    _seed_job(store, platform_result=None)
    dests = DestinationStore(ws.destinations_path())
    dest = dests.create(name="Main", folder_id="fld")
    exports = ExportStore(ws.exports_dir())
    exports.save(ExportJob(
        export_id="exp_live", destination_id=dest.id, folder_id="fld",
        state="succeeded", created_utc="2026-08-22T08:00:00Z",
        files=[_ok_file()],
    ))
    resp = client.get("/api/drive/exports")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    pack = body[0]
    assert pack["export_id"] == "exp_live"
    assert pack["destination_name"] == "Main"
    assert pack["count"] == 1
    assert pack["outcome"] == "pass"
    assert pack["files"][0]["variant_id"] == "s1:1"
    assert pack["files"][0]["job_id"] == "j1"
    assert "ignored-caption" not in str(pack)
