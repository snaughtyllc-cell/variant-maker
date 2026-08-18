import json

from farm_fakes import FakeDrive
from fastapi.testclient import TestClient

from tests.server.fakes import FakeRunner
from variant_maker.server.app import create_app
from variant_maker.server.jobs import JobStore
from variant_maker.server.workspace import Workspace


def _app(tmp_path, drive=None):
    ws = Workspace(str(tmp_path))
    store = JobStore(ws, FakeRunner({}))
    sa = tmp_path / "sa.json"
    sa.write_text(json.dumps({"client_email": "bot@x.iam.gserviceaccount.com"}))
    client = TestClient(create_app(
        store, drive=drive or FakeDrive(), sa_json_path=str(sa),
        enable_workflow_poller=False,
    ))
    return client, store, ws


def _dest(client, drive, name):
    folder = drive.make_folder(name)
    dest = client.post("/api/drive/destinations", json={
        "name": name, "folder_url": folder,
    }).json()
    return dest, folder


def _folders(drive, parent):
    return [f for f in drive.list_files(parent) if f.is_folder]


def test_workflow_crud(tmp_path):
    drive = FakeDrive()
    client, _, _ = _app(tmp_path, drive)
    inbox, _ = _dest(client, drive, "Inbox")
    out, _ = _dest(client, drive, "Out")
    resp = client.post("/api/workflows", json={
        "name": "Reels pack",
        "inbox_destination_id": inbox["id"],
        "output_destination_id": out["id"],
        "count": 5,
        "quality_mode": "fast",
        "enabled": True,
        "poll_seconds": 120,
    })
    assert resp.status_code == 201
    wf = resp.json()
    assert wf["name"] == "Reels pack"
    assert wf["count"] == 5
    assert wf["enabled"] is True
    listed = client.get("/api/workflows").json()
    assert len(listed) == 1
    patched = client.patch(f"/api/workflows/{wf['id']}", json={"enabled": False}).json()
    assert patched["enabled"] is False
    assert client.delete(f"/api/workflows/{wf['id']}").status_code == 204
    assert client.get("/api/workflows").json() == []


def test_workflow_rejects_unknown_destination(tmp_path):
    drive = FakeDrive()
    client, _, _ = _app(tmp_path, drive)
    inbox, _ = _dest(client, drive, "Inbox")
    resp = client.post("/api/workflows", json={
        "name": "x",
        "inbox_destination_id": inbox["id"],
        "output_destination_id": "dst_missing",
    })
    assert resp.status_code == 400


def test_workflow_run_exports_new_inbox_video(tmp_path):
    drive = FakeDrive()
    client, store, _ = _app(tmp_path, drive)
    inbox_dest, inbox = _dest(client, drive, "Inbox")
    out_dest, out = _dest(client, drive, "Out")
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"workflow-clip")
    drive.put_file("clip.mp4", str(clip), parent=inbox)
    wf = client.post("/api/workflows", json={
        "name": "Auto",
        "inbox_destination_id": inbox_dest["id"],
        "output_destination_id": out_dest["id"],
        "count": 2,
        "poll_seconds": 60,
    }).json()

    first = client.post(f"/api/workflows/{wf['id']}/run")
    assert first.status_code == 200
    summary = first.json()["last_summary"]
    assert summary["queued"] + summary["exported"] >= 1
    for jid in summary["job_ids"]:
        store.wait(jid, timeout=5)
    if summary["exported"] < 1:
        second = client.post(f"/api/workflows/{wf['id']}/run")
        summary = second.json()["last_summary"]
    assert summary["exported"] >= 1

    subs = _folders(drive, out)
    assert len(subs) == 1
    assert subs[0].name.startswith("clip__")
    names = {c.name for c in drive.list_files(subs[0].id)}
    assert "manifest.json" in names
    assert any(n.endswith(".mp4") for n in names)

    again = client.post(f"/api/workflows/{wf['id']}/run").json()["last_summary"]
    assert again["skipped"] >= 1
    assert again["queued"] == 0
    assert len(_folders(drive, out)) == 1


def test_workflow_run_unknown_404(tmp_path):
    client, _, _ = _app(tmp_path)
    assert client.post("/api/workflows/wf_nope/run").status_code == 404
