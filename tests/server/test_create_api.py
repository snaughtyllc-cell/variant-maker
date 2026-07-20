"""Create-mode API contract tests (TDD) — fakes only, no Comfy/LLM/network."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from tests.server.create_fakes import FakeCreateRunner
from variant_maker.server.app import create_app
from variant_maker.server.create_api import CreateJobStore
from variant_maker.server.workspace import Workspace


def _client(tmp_path, runner=None):
    store = CreateJobStore(
        Workspace(str(tmp_path / "create")),
        runner or FakeCreateRunner(),
    )
    return TestClient(create_app(create_store=store)), store


def test_create_job_returns_201_and_job_id(tmp_path):
    client, store = _client(tmp_path)
    resp = client.post(
        "/api/create/jobs",
        data={"brief": "mirror selfie soft flash", "aspect": "9:16", "count": "2"},
        files=[("face_refs", ("face.jpg", b"facebytes", "image/jpeg"))],
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["job_id"]
    assert body["state"] == "running"
    assert body["brief"] == "mirror selfie soft flash"
    assert body["aspect"] == "9:16"
    assert body["count"] == 2
    store.wait(body["job_id"], timeout=5)


def test_create_job_requires_brief_and_face_ref(tmp_path):
    client, _ = _client(tmp_path)
    missing_brief = client.post(
        "/api/create/jobs",
        data={"aspect": "9:16", "count": "1"},
        files=[("face_refs", ("face.jpg", b"x", "image/jpeg"))],
    )
    assert missing_brief.status_code == 422

    missing_face = client.post(
        "/api/create/jobs",
        data={"brief": "hotel bathroom", "aspect": "9:16", "count": "1"},
    )
    assert missing_face.status_code in (400, 422)


def test_get_create_job_detail_lists_stills_and_handoff(tmp_path):
    client, store = _client(tmp_path)
    job_id = client.post(
        "/api/create/jobs",
        data={"brief": "creator in cafe", "aspect": "9:16", "count": "2"},
        files=[("face_refs", ("a.jpg", b"a", "image/jpeg"))],
    ).json()["job_id"]
    assert store.wait(job_id, timeout=5)
    detail = client.get(f"/api/create/jobs/{job_id}").json()
    assert detail["state"] == "done"
    assert detail["phase"] == "done"
    assert len(detail["stills"]) == 2
    assert detail["stills"][0]["filename"] == "still_01.png"
    assert detail["stills"][0]["handoff_filename"] == "still_01.mp4"
    assert detail["stills"][0]["file_url"].endswith("/still_01.png")
    assert detail["stills"][0]["handoff_url"].endswith("/still_01.mp4")
    assert detail["prompt"]["positive"] == "fake positive"


def test_get_unknown_create_job_404(tmp_path):
    client, _ = _client(tmp_path)
    assert client.get("/api/create/jobs/nope").status_code == 404


def test_create_sse_events_stream_until_job_done(tmp_path):
    client, store = _client(tmp_path)
    job_id = client.post(
        "/api/create/jobs",
        data={"brief": "soft light", "aspect": "1:1", "count": "1"},
        files=[("face_refs", ("f.jpg", b"f", "image/jpeg"))],
    ).json()["job_id"]
    store.wait(job_id, timeout=5)
    with client.stream("GET", f"/api/create/jobs/{job_id}/events") as r:
        payloads = []
        for line in r.iter_lines():
            if line.startswith("data:"):
                payloads.append(json.loads(line[len("data:"):].strip()))
                if payloads[-1].get("state") == "job-done":
                    break
    states = [p.get("state") for p in payloads]
    assert "expanding" in states
    assert "generating" in states
    assert states.count("done") == 1
    assert states[-1] == "job-done"


def test_serve_create_still_and_handoff_files(tmp_path):
    client, store = _client(tmp_path)
    job_id = client.post(
        "/api/create/jobs",
        data={"brief": "vertical selfie", "aspect": "9:16", "count": "1"},
        files=[("face_refs", ("f.jpg", b"f", "image/jpeg"))],
    ).json()["job_id"]
    store.wait(job_id, timeout=5)
    still = client.get(f"/api/create/jobs/{job_id}/files/still_01.png")
    handoff = client.get(f"/api/create/jobs/{job_id}/files/still_01.mp4")
    assert still.status_code == 200
    assert still.content == b"fake-png"
    assert handoff.status_code == 200
    assert handoff.content == b"fake-mp4"


def test_create_job_rejects_count_out_of_range(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.post(
        "/api/create/jobs",
        data={"brief": "x", "aspect": "9:16", "count": "5"},
        files=[("face_refs", ("f.jpg", b"f", "image/jpeg"))],
    )
    assert resp.status_code == 422


def test_mount_create_routes_on_app():
    """create router mounts without rewriting Spoof job routes."""
    app = create_app()
    client = TestClient(app)
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/jobs").status_code == 200  # Spoof list still works
    # Create detail 404 proves create router is mounted (not a missing-route 404 from Spoof)
    resp = client.get("/api/create/jobs/nope")
    assert resp.status_code == 404
    assert "create job" in resp.json()["detail"]
