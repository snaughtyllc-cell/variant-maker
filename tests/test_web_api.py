"""Studio web API — pack-split Drive export (no live Drive)."""
from pathlib import Path

from farm_fakes import FakeDrive
from fastapi.testclient import TestClient
from tests.server.fakes import FakeRunner
from variant_maker.server.app import create_app
from variant_maker.server.jobs import Job, JobSource, JobStore, VariantInfo
from variant_maker.server.workspace import Workspace


def _app(tmp_path, drive=None, sa_path=None):
    ws = Workspace(str(tmp_path))
    store = JobStore(ws, FakeRunner({}))
    if sa_path is None:
        sa_path = tmp_path / "sa.json"
        sa_path.write_text('{"client_email": "bot@x.iam.gserviceaccount.com"}')
    return TestClient(create_app(store, drive=drive or FakeDrive(), sa_json_path=str(sa_path))), store, ws


def _seed_pack(store, ws, *, job_id="j1", source_id="s1", n=20):
    job = Job(job_id=job_id, count=n, created_utc="Z", state="done")
    src = JobSource(source_id=source_id, filename="a.mp4", requested=n)
    out = ws.source_out_dir(job_id, source_id)
    for i in range(1, n + 1):
        name = f"v{i:02d}.mp4"
        Path(out, name).write_bytes(b"vid")
        src.variants.append(VariantInfo(
            source_id=source_id, index=i, filename=name, status="ok", quality={},
        ))
    job.sources.append(src)
    store._jobs[job_id] = job
    store._source_index[source_id] = (job_id, src)
    return src


def _dest(client, drive, name):
    folder = drive.make_folder(name)
    return client.post("/api/drive/destinations", json={"name": name, "folder_url": folder}).json(), folder


def _split_payload(resp):
    raw = resp.json()
    if isinstance(raw, dict) and "jobs" in raw:
        return raw
    return {"ok": True, "jobs": raw, "split": None}


def _job_id(job: dict) -> str:
    return job.get("id") or job.get("export_id")


def _job_dest(job: dict) -> str:
    return job.get("dest") or job.get("destination_id")


def _job_names(job: dict) -> list[str]:
    files = job.get("files") or []
    if files and isinstance(files[0], dict):
        return [f["filename"] for f in files]
    return list(files)


def _job_count(job: dict) -> int:
    if "count" in job:
        return int(job["count"])
    return len(job.get("files") or [])


def _wait(client, export_id):
    import time
    detail = None
    for _ in range(80):
        detail = client.get(f"/api/drive/exports/{export_id}").json()
        if detail["state"] in ("succeeded", "partial", "failed"):
            return detail
        time.sleep(0.05)
    return detail


def test_existing_single_destination_export_still_works(tmp_path):
    drive = FakeDrive()
    client, store, ws = _app(tmp_path, drive=drive)
    dest, folder = _dest(client, drive, "Out")
    _seed_pack(store, ws, n=1)
    resp = client.post("/api/drive/exports", json={
        "destination_id": dest["id"],
        "variants": [{"source_id": "s1", "index": 1}],
    })
    assert resp.status_code == 201
    assert resp.json()["destination_id"] == dest["id"]
    detail = _wait(client, resp.json()["export_id"])
    assert detail["state"] == "succeeded"
    assert any(f.name == "v01.mp4" for f in drive.list_files(folder))


def test_split_export_partitions_20_pack_across_three_dests(tmp_path):
    drive = FakeDrive()
    client, store, ws = _app(tmp_path, drive=drive)
    main, main_folder = _dest(client, drive, "Maya / main")
    trial, trial_folder = _dest(client, drive, "Maya / trial")
    growth, growth_folder = _dest(client, drive, "Maya / growth")
    _seed_pack(store, ws, n=20)
    resp = client.post("/api/drive/exports/split", json={
        "job_id": "j1",
        "selected": [{"source_id": "s1", "index": i} for i in range(1, 21)],
        "destinations": [
            {"destination_id": main["id"], "label": "main"},
            {"destination_id": trial["id"], "label": "trial"},
            {"destination_id": growth["id"], "label": "growth"},
        ],
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["ok"] is True
    jobs = body["jobs"]
    assert len(jobs) == 3
    assert [j["count"] for j in jobs] == [7, 7, 6]
    assert [j["dest"] for j in jobs] == [main["id"], trial["id"], growth["id"]]
    assert jobs[0]["files"] == [f"v{i:02d}.mp4" for i in range(1, 8)]
    assert jobs[1]["files"] == [f"v{i:02d}.mp4" for i in range(8, 15)]
    assert jobs[2]["files"] == [f"v{i:02d}.mp4" for i in range(15, 21)]
    for job in jobs:
        assert _wait(client, job["id"])["state"] == "succeeded"
    main_names = {f.name for f in drive.list_files(main_folder)}
    trial_names = {f.name for f in drive.list_files(trial_folder)}
    growth_names = {f.name for f in drive.list_files(growth_folder)}
    assert main_names == {f"v{i:02d}.mp4" for i in range(1, 8)}
    assert trial_names == {f"v{i:02d}.mp4" for i in range(8, 15)}
    assert growth_names == {f"v{i:02d}.mp4" for i in range(15, 21)}
    assert not (main_names & trial_names)
    assert not (main_names & growth_names)
    assert not (trial_names & growth_names)


def test_split_export_two_dests_and_consume_bank_once(tmp_path):
    drive = FakeDrive()
    client, store, ws = _app(tmp_path, drive=drive)
    main, _ = _dest(client, drive, "main")
    trial, _ = _dest(client, drive, "trial")
    _seed_pack(store, ws, n=20)
    for i in range(30):
        client.post("/api/captions", json={"text": f"cap {i}"})
    before = client.get("/api/captions").json()
    assert before["remaining"] == 30
    resp = client.post("/api/drive/exports/split", json={
        "job_id": "j1",
        "selected": [{"source_id": "s1", "index": i} for i in range(1, 21)],
        "destinations": [
            {"destination_id": main["id"], "label": "main"},
            {"destination_id": trial["id"], "label": "trial"},
        ],
        "consume_bank": True,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert [j["count"] for j in body["jobs"]] == [10, 10]
    after = client.get("/api/captions").json()
    assert after["cursor"] == 20
    assert after["remaining"] == 10


def test_split_export_skips_empty_slice(tmp_path):
    drive = FakeDrive()
    client, store, ws = _app(tmp_path, drive=drive)
    a, folder_a = _dest(client, drive, "A")
    b, folder_b = _dest(client, drive, "B")
    c, folder_c = _dest(client, drive, "C")
    _seed_pack(store, ws, n=2)
    resp = client.post("/api/drive/exports/split", json={
        "job_id": "j1",
        "selected": [{"source_id": "s1", "index": 1}, {"source_id": "s1", "index": 2}],
        "destinations": [
            {"destination_id": a["id"], "label": "main"},
            {"destination_id": b["id"], "label": "trial"},
            {"destination_id": c["id"], "label": "growth"},
        ],
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["split"] == [[1], [2], []]
    assert [j["count"] for j in body["jobs"]] == [1, 1]
    for job in body["jobs"]:
        assert _wait(client, job["id"])["state"] == "succeeded"
    assert {f.name for f in drive.list_files(folder_a)} == {"v01.mp4"}
    assert {f.name for f in drive.list_files(folder_b)} == {"v02.mp4"}
    assert drive.list_files(folder_c) == []


def test_split_export_allows_one_dest_and_rejects_bad_job(tmp_path):
    drive = FakeDrive()
    client, store, ws = _app(tmp_path, drive=drive)
    dest, _ = _dest(client, drive, "Out")
    _seed_pack(store, ws, n=4)
    selected = [{"source_id": "s1", "index": i} for i in range(1, 5)]
    one = client.post("/api/drive/exports/split", json={
        "job_id": "j1",
        "selected": selected,
        "destinations": [{"destination_id": dest["id"], "label": "main", "count": 4}],
    })
    assert one.status_code == 201
    assert one.json()["jobs"][0]["count"] == 4
    other, _ = _dest(client, drive, "Trial")
    missing_job = client.post("/api/drive/exports/split", json={
        "job_id": "nope",
        "selected": selected,
        "destinations": [
            {"destination_id": dest["id"], "label": "main"},
            {"destination_id": other["id"], "label": "trial"},
        ],
    })
    assert missing_job.status_code == 404

    ws2 = Workspace(str(tmp_path / "nodrive"))
    store2 = JobStore(ws2, FakeRunner({}))
    bare = TestClient(create_app(store2, drive=None, sa_json_path=""))
    unauth = bare.post("/api/drive/exports/split", json={
        "job_id": "j1",
        "selected": selected,
        "destinations": [
            {"destination_id": "d1", "label": "main"},
            {"destination_id": "d2", "label": "trial"},
        ],
    })
    assert unauth.status_code == 503
