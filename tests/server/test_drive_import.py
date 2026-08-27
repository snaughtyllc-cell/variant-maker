import json

from farm_fakes import FakeDrive
from fastapi.testclient import TestClient

from tests.server.fakes import FakeRunner
from variant_maker.server.app import create_app
from variant_maker.server.jobs import JobStore
from variant_maker.server.workspace import Workspace


def _app(tmp_path, drive=None, sa_path=None):
    ws = Workspace(str(tmp_path))
    store = JobStore(ws, FakeRunner({}))
    if sa_path is None:
        sa_path = tmp_path / "sa.json"
        sa_path.write_text(json.dumps({"client_email": "bot@x.iam.gserviceaccount.com"}))
    return TestClient(create_app(store, drive=drive or FakeDrive(), sa_json_path=str(sa_path))), store, ws


def _dest(client, drive, name="Inbox"):
    folder = drive.make_folder(name)
    dest = client.post("/api/drive/destinations", json={
        "name": name, "folder_url": folder,
    }).json()
    return dest, folder


def test_list_destination_videos_skips_folders_and_docs(tmp_path):
    drive = FakeDrive()
    client, _, _ = _app(tmp_path, drive=drive)
    dest, folder = _dest(client, drive)
    clip = tmp_path / "a.mp4"
    clip.write_bytes(b"vid")
    notes = tmp_path / "notes.txt"
    notes.write_text("nope")
    drive.put_file("a.mp4", str(clip), parent=folder)
    drive.put_file("notes.txt", str(notes), parent=folder, mime_type="text/plain")
    drive.make_folder("sub", parent=folder)

    resp = client.get(f"/api/drive/destinations/{dest['id']}/videos")
    assert resp.status_code == 200
    names = {v["name"] for v in resp.json()["videos"]}
    assert names == {"a.mp4"}


def test_list_destination_videos_404(tmp_path):
    client, _, _ = _app(tmp_path)
    assert client.get("/api/drive/destinations/dst_nope/videos").status_code == 404


def test_from_drive_creates_job(tmp_path):
    drive = FakeDrive()
    client, store, _ = _app(tmp_path, drive=drive)
    dest, folder = _dest(client, drive)
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video-bytes")
    fid = drive.put_file("clip.mp4", str(clip), parent=folder)

    resp = client.post("/api/jobs/from-drive", json={
        "destination_id": dest["id"],
        "file_ids": [fid],
        "count": 2,
        "quality_mode": "fast",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["sources"][0]["filename"] == "clip.mp4"
    assert body["sources"][0]["requested"] == 2
    store.wait(body["job_id"], timeout=5)
    job = store.get(body["job_id"])
    assert job is not None and job.state == "done"
    assert store._runner.last_quality_mode == "fast"


def test_from_drive_generate_captions_uses_seed(tmp_path):
    drive = FakeDrive()
    client, store, _ = _app(tmp_path, drive=drive)
    dest, folder = _dest(client, drive)
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video-bytes")
    fid = drive.put_file("clip.mp4", str(clip), parent=folder)
    seed = "POV boil #reels"

    resp = client.post("/api/jobs/from-drive", json={
        "destination_id": dest["id"],
        "file_ids": [fid],
        "count": 2,
        "generate_captions": True,
        "caption_seed": seed,
    })
    assert resp.status_code == 201
    store.wait(resp.json()["job_id"], timeout=5)
    job = store.get(resp.json()["job_id"])
    caps = [v.caption for v in job.sources[0].variants]
    assert caps[0] == seed
    assert "POV boil" in caps[1]


def test_from_drive_rejects_file_outside_folder(tmp_path):
    drive = FakeDrive()
    client, _, _ = _app(tmp_path, drive=drive)
    dest, _folder = _dest(client, drive)
    other = drive.make_folder("other")
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"x")
    fid = drive.put_file("clip.mp4", str(clip), parent=other)
    resp = client.post("/api/jobs/from-drive", json={
        "destination_id": dest["id"],
        "file_ids": [fid],
        "count": 1,
    })
    assert resp.status_code == 400
    assert "folder" in resp.json()["detail"].lower()


def test_from_drive_requires_file_ids(tmp_path):
    drive = FakeDrive()
    client, _, _ = _app(tmp_path, drive=drive)
    dest, _ = _dest(client, drive)
    resp = client.post("/api/jobs/from-drive", json={
        "destination_id": dest["id"],
        "file_ids": [],
        "count": 1,
    })
    assert resp.status_code == 400
