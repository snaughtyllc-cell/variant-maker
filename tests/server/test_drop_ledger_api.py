"""Drop Ledger API: ensure/sync + platform_result write-through (FakeSheets)."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from tests.server.fakes import FakeRunner
from variant_maker.server.app import create_app
from variant_maker.server.jobs import JobStore
from variant_maker.server.sheets import FakeSheets
from variant_maker.server.workspace import Workspace


def _seed_manifest(ws_root, job_id: str, source_id: str, n: int = 2) -> None:
    out = ws_root / "jobs" / job_id / source_id / "out"
    out.mkdir(parents=True)
    inn = ws_root / "jobs" / job_id / source_id / "in"
    inn.mkdir(parents=True)
    (inn / "clip.mp4").write_bytes(b"x")
    variants = []
    for i in range(1, n + 1):
        variants.append({
            "index": i,
            "filename": f"clip_v{i:02d}.mp4",
            "status": "ok",
            "uniqueness": 0.4 + i * 0.01,
            "quality": {"vmaf": 90 + i},
            "seed": i,
            "params": {"video": {"crop_keep": 0.96}},
            "platform_result": None,
        })
    (out / "manifest.json").write_text(json.dumps({
        "created_utc": "2026-07-30T03:00:00Z",
        "source": {"path": "clip.mp4"},
        "run": {"platform": "tiktok", "count": n},
        "variants": variants,
    }))


def test_drop_ledger_sync_seeds_rows(tmp_path):
    sheets = FakeSheets()
    store = JobStore(Workspace(str(tmp_path)), FakeRunner({}))
    _seed_manifest(tmp_path, "jobaaa111222", "srcbbb333444", n=2)
    client = TestClient(create_app(store, sheets=sheets, sa_json_path="", hydrate=True))

    status = client.get("/api/drop-ledger/status").json()
    assert status["configured"] is False
    assert "Ensure" in status["message"]
    assert "POST /api" not in status["message"]

    sync = client.post("/api/drop-ledger/sync", json={
        "job_ids": ["jobaaa111222"], "ensure": True,
    })
    assert sync.status_code == 200, sync.text
    body = sync.json()
    assert body["rows"] == 2
    assert body["inserted"] == 2
    assert body["spreadsheet_url"].startswith("https://docs.google.com/spreadsheets/d/")

    status2 = client.get("/api/drop-ledger/status").json()
    assert status2["configured"] is True
    assert status2["spreadsheet_id"] == body["spreadsheet_id"]

    # Re-sync is idempotent (no wipe)
    sync2 = client.post("/api/drop-ledger/sync", json={
        "job_ids": ["jobaaa111222"], "ensure": True,
    }).json()
    assert sync2["inserted"] == 0
    assert sync2["unchanged"] == 2


def test_platform_result_writes_through_to_sheet(tmp_path):
    sheets = FakeSheets()
    store = JobStore(Workspace(str(tmp_path)), FakeRunner({}))
    client = TestClient(create_app(store, sheets=sheets, sa_json_path="", hydrate=False))

    job_id = client.post(
        "/api/jobs",
        files=[("files", ("a.mp4", b"x", "video/mp4"))],
        data={"count": "1"},
    ).json()["job_id"]
    store.wait(job_id, timeout=5)
    src = client.get(f"/api/jobs/{job_id}").json()["sources"][0]
    sid = src["source_id"]
    index = src["variants"][0]["index"]

    # Seed ledger first so the row exists
    client.post("/api/drop-ledger/sync", json={"job_ids": [job_id], "ensure": True})

    resp = client.post(f"/api/variants/{sid}/{index}/platform-result",
                       json={"result": "passed"})
    assert resp.status_code == 200
    assert resp.json()["platform_result"] == "passed"

    # Find the sheet and check platform_result column
    sheet_id = client.get("/api/drop-ledger/status").json()["spreadsheet_id"]
    values = sheets.get_values(sheet_id, "A:U")
    # header + 1 data row
    assert values[1][10] == "passed"  # platform_result column
    assert values[0][-1] == "post_url"


def test_post_url_writes_through_to_sheet(tmp_path):
    sheets = FakeSheets()
    store = JobStore(Workspace(str(tmp_path)), FakeRunner({}))
    client = TestClient(create_app(store, sheets=sheets, sa_json_path="", hydrate=False))

    job_id = client.post(
        "/api/jobs",
        files=[("files", ("a.mp4", b"x", "video/mp4"))],
        data={"count": "1"},
    ).json()["job_id"]
    store.wait(job_id, timeout=5)
    src = client.get(f"/api/jobs/{job_id}").json()["sources"][0]
    sid = src["source_id"]
    index = src["variants"][0]["index"]
    client.post("/api/drop-ledger/sync", json={"job_ids": [job_id], "ensure": True})

    url = "https://www.instagram.com/reel/AbC123/"
    resp = client.post(f"/api/variants/{sid}/{index}/post-url", json={"url": url})
    assert resp.status_code == 200
    assert resp.json()["post_url"] == url

    sheet_id = client.get("/api/drop-ledger/status").json()["spreadsheet_id"]
    values = sheets.get_values(sheet_id, "A:U")
    assert values[0][-1] == "post_url"
    assert values[1][-1] == url


def test_drop_ledger_status_asks_to_connect_google_when_sheets_missing(tmp_path):
    store = JobStore(Workspace(str(tmp_path)), FakeRunner({}))
    client = TestClient(create_app(store, sheets=None, sa_json_path="", hydrate=True))
    status = client.get("/api/drop-ledger/status").json()
    assert status["configured"] is False
    assert "Connect Google" in status["message"]
    assert "POST /api" not in status["message"]


def test_hydrate_from_disk_restores_gallery(tmp_path):
    _seed_manifest(tmp_path, "hydratedjob01", "hydratedsrc01", n=3)
    store = JobStore(Workspace(str(tmp_path)), FakeRunner({}))
    assert store.hydrate_from_disk() == 1
    client = TestClient(create_app(store, sheets=FakeSheets(), sa_json_path="", hydrate=False))
    jobs = client.get("/api/jobs").json()
    assert any(j["job_id"] == "hydratedjob01" for j in jobs)
    detail = client.get("/api/jobs/hydratedjob01").json()
    assert len(detail["sources"][0]["variants"]) == 3
