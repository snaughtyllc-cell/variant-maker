"""Object-storage delivery: Railway issues signed URLs and never copies MP4s."""
from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime, timedelta

from farm_fakes import FakeDrive
from fastapi.testclient import TestClient

from tests.server.fakes import FakeObjectStore, FakeRunner
from variant_maker.server.app import create_app
from variant_maker.server.drive_exports import (
    ExportRunner,
    ExportStore,
    VariantRef,
    build_export_files,
)
from variant_maker.server.jobs import Job, JobSource, JobStore, VariantInfo
from variant_maker.server.workspace import Workspace


def test_direct_upload_returns_presigned_put_and_starts_job(tmp_path):
    blob = FakeObjectStore()
    store = JobStore(Workspace(str(tmp_path)), FakeRunner({}), object_store=blob)
    client = TestClient(create_app(store))
    init = client.post(
        "/api/uploads/direct",
        data={"filename": "clip.mp4", "size": "12", "content_type": "video/mp4"},
    )
    assert init.status_code == 200
    body = init.json()
    assert body["mode"] == "direct"
    assert body["url"].startswith("https://objects.test/put/")
    key = body["key"]
    blob.put_bytes(key, b"direct-src")
    resp = client.post(
        "/api/jobs/from-object",
        json={
            "items": [{"filename": "clip.mp4", "key": key}],
            "count": 1,
        },
    )
    assert resp.status_code == 201
    job_id = resp.json()["job_id"]
    store.wait(job_id, timeout=5)
    job = store.get(job_id)
    assert job.sources[0].source_object_key.startswith("inputs/")
    assert job.telemetry.get("processing_charge") == "Fast 1 pack"


def test_local_upload_fallback_without_object_store(tmp_path):
    store = JobStore(Workspace(str(tmp_path)), FakeRunner({}))
    client = TestClient(create_app(store))
    init = client.post(
        "/api/uploads/direct",
        data={"filename": "clip.mp4", "size": "4"},
    )
    assert init.json()["mode"] == "local"
    assert "upload_id" in init.json()


def test_finished_job_records_runpod_telemetry_fields(tmp_path):
    store = JobStore(
        Workspace(str(tmp_path)), FakeRunner({}), workspace_id="ws_lab",
    )
    job = store.create_job([("a.mp4", b"xxxx")], count=2)
    store.wait(job.job_id, timeout=5)
    tel = job.telemetry
    assert tel["workspace_id"] == "ws_lab"
    assert tel["requested"] == 2
    assert tel["processing_charge"] == "Fast 2 pack"
    assert tel["delivery_destination"] == "download"
    assert tel.get("completed_utc")
    assert job.outputs_expires_utc


def test_prune_expired_outputs_keeps_job_metadata(tmp_path):
    blob = FakeObjectStore()
    blob.put_bytes("outputs/s1/v01.mp4", b"mp4-bytes")
    store = JobStore(Workspace(str(tmp_path)), FakeRunner({}), object_store=blob)
    job = store.create_job([("a.mp4", b"xxxx")], count=1)
    store.wait(job.job_id, timeout=5)
    sid = job.sources[0].source_id
    blob.put_bytes(f"outputs/{sid}/v01.mp4", b"mp4-bytes")
    job.outputs_expires_utc = (
        datetime.now(UTC) - timedelta(hours=1)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    job.telemetry["outputs_deleted"] = False
    store.prune_expired_outputs()
    assert store.get(job.job_id) is not None
    assert job.telemetry.get("outputs_deleted") is True
    assert blob.list_prefix(f"outputs/{sid}/") == []


def test_zip_ok_variants_skips_local_archive_when_object_store_holds_files(tmp_path):
    blob = FakeObjectStore()
    store = JobStore(Workspace(str(tmp_path)), FakeRunner({}), object_store=blob)
    job = store.create_job([("a.mp4", b"xxxx")], count=1)
    store.wait(job.job_id, timeout=5)
    sid = job.sources[0].source_id
    blob.put_bytes(f"outputs/{sid}/v01.mp4", b"mp4-bytes")
    assert store.zip_ok_variants(sid) is None
    assert store._keep_local_media is False


def test_from_drive_skips_volume_when_object_store_is_set(tmp_path):
    drive = FakeDrive()
    blob = FakeObjectStore()
    ws = Workspace(str(tmp_path))
    store = JobStore(ws, FakeRunner({}), object_store=blob)
    sa = tmp_path / "sa.json"
    sa.write_text(json.dumps({"client_email": "bot@x.iam.gserviceaccount.com"}))
    client = TestClient(create_app(store, drive=drive, sa_json_path=str(sa)))
    folder = drive.make_folder("Inbox")
    dest = client.post("/api/drive/destinations", json={
        "name": "Inbox", "folder_url": folder,
    }).json()
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video-bytes")
    fid = drive.put_file("clip.mp4", str(clip), parent=folder)
    resp = client.post("/api/jobs/from-drive", json={
        "destination_id": dest["id"],
        "file_ids": [fid],
        "count": 1,
    })
    assert resp.status_code == 201
    job = store.get(resp.json()["job_id"])
    assert job.sources[0].drive_file_id == fid
    local = ws.source_in_path(job.job_id, job.sources[0].source_id, "clip.mp4")
    assert not os.path.isfile(local)
    store.wait(job.job_id, timeout=5)
    assert job.state == "done"


def test_export_runner_uses_remote_deliver_without_object_get(tmp_path):
    blob = FakeObjectStore()
    blob.put_bytes("outputs/s1/v01.mp4", b"video-bytes")
    ws = Workspace(str(tmp_path))
    store = JobStore(ws, FakeRunner({}), object_store=blob)
    job = Job(job_id="j1", count=1, created_utc="2026-01-01T00:00:00Z", state="done")
    src = JobSource(source_id="s1", filename="a.mp4", requested=1)
    src.variants.append(VariantInfo(
        source_id="s1", index=1, filename="v01.mp4", status="ok",
        quality={"vmaf": 95}, object_key="outputs/s1/v01.mp4",
    ))
    job.sources.append(src)
    store._jobs["j1"] = job
    store._source_index["s1"] = ("j1", src)
    files = build_export_files(store, [VariantRef("s1", 1)])
    exports = ExportStore(ws.exports_dir())
    drive = FakeDrive()
    folder = drive.make_folder("out")
    exp = exports.create(destination_id="dst", folder_id=folder, files=files)
    got = {}

    def remote(**kw):
        got.update(kw)
        return {"delivered": [{"key": "outputs/s1/v01.mp4", "name": "v01.mp4", "drive_file_id": "drv1"}]}

    ExportRunner(
        drive, exports, object_store=blob,
        remote_deliver=remote, mint_token=lambda: "ya29.job",
    ).start(exp)
    for _ in range(50):
        exp = exports.get(exp.export_id)
        if exp.state in ("succeeded", "partial", "failed"):
            break
        time.sleep(0.05)
    assert exp.state == "succeeded"
    assert got["access_token"] == "ya29.job"
    assert blob.gets == []

