import json

from fastapi.testclient import TestClient

from variant_maker.server.app import create_app
from variant_maker.server.jobs import JobStore
from variant_maker.server.workspace import Workspace
from tests.server.fakes import FakeRunner


def test_health_ok():
    client = TestClient(create_app())
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def _client(tmp_path, plan=None):
    store = JobStore(Workspace(str(tmp_path)), FakeRunner(plan or {}))
    return TestClient(create_app(store)), store


def test_create_job_returns_sources(tmp_path):
    client, store = _client(tmp_path)
    resp = client.post(
        "/api/jobs",
        files=[("files", ("a.mp4", b"x", "video/mp4")),
               ("files", ("b.mp4", b"y", "video/mp4"))],
        data={"count": "3"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["sources"]) == 2
    assert body["sources"][0]["requested"] == 3
    store.wait(body["job_id"], timeout=5)


def test_get_job_detail_shows_ok_variants_and_counts(tmp_path):
    client, store = _client(tmp_path, plan={2: "best_effort"})
    job_id = client.post("/api/jobs",
                         files=[("files", ("a.mp4", b"x", "video/mp4"))],
                         data={"count": "3"}).json()["job_id"]
    store.wait(job_id, timeout=5)
    detail = client.get(f"/api/jobs/{job_id}").json()
    src = detail["sources"][0]
    assert src["delivered"] == 2 and src["shortfall"] == 1
    assert [v["status"] for v in src["variants"]] == ["ok", "ok"]  # ok-only in cards


def test_get_unknown_job_404(tmp_path):
    client, _ = _client(tmp_path)
    assert client.get("/api/jobs/nope").status_code == 404


def test_sse_events_stream_until_job_done(tmp_path):
    client, store = _client(tmp_path)
    job_id = client.post("/api/jobs",
                         files=[("files", ("a.mp4", b"x", "video/mp4"))],
                         data={"count": "2"}).json()["job_id"]
    store.wait(job_id, timeout=5)
    # stream is replayable from the recorded event log after completion
    with client.stream("GET", f"/api/jobs/{job_id}/events") as r:
        payloads = []
        for line in r.iter_lines():
            if line.startswith("data:"):
                payloads.append(json.loads(line[len("data:"):].strip()))
                if payloads[-1].get("state") == "job-done":
                    break
    states = [p.get("state") for p in payloads]
    assert states.count("done") == 2
    assert states[-1] == "job-done"


def test_gallery_groups_sources_ok_only(tmp_path):
    client, store = _client(tmp_path, plan={2: "best_effort"})
    job_id = client.post("/api/jobs",
                         files=[("files", ("a.mp4", b"x", "video/mp4"))],
                         data={"count": "3"}).json()["job_id"]
    store.wait(job_id, timeout=5)
    gallery = client.get("/api/gallery").json()
    assert len(gallery) == 1
    assert gallery[0]["delivered"] == 2
    assert gallery[0]["shortfall"] == 1
    assert all(v["status"] == "ok" for v in gallery[0]["variants"])


def test_diagnostics_lists_non_ok(tmp_path):
    client, store = _client(tmp_path, plan={2: "best_effort", 3: "best_effort"})
    job_id = client.post("/api/jobs",
                         files=[("files", ("a.mp4", b"x", "video/mp4"))],
                         data={"count": "3"}).json()["job_id"]
    store.wait(job_id, timeout=5)
    diag = client.get("/api/diagnostics").json()
    assert len(diag) == 2
    assert all(d["status"] == "best_effort" for d in diag)


def test_serve_variant_and_source_files(tmp_path):
    client, store = _client(tmp_path)
    job_id = client.post("/api/jobs",
                         files=[("files", ("a.mp4", b"orig", "video/mp4"))],
                         data={"count": "1"}).json()["job_id"]
    store.wait(job_id, timeout=5)
    src = client.get(f"/api/jobs/{job_id}").json()["sources"][0]
    fname = src["variants"][0]["filename"]
    sid = src["source_id"]
    assert client.get(f"/api/variants/{sid}/{fname}").status_code == 200
    assert client.get(f"/api/sources/{sid}/source").content == b"orig"
    assert client.get("/api/variants/nope/x.mp4").status_code == 404


def test_regenerate_endpoint(tmp_path):
    client, store = _client(tmp_path)
    job_id = client.post("/api/jobs",
                         files=[("files", ("a.mp4", b"x", "video/mp4"))],
                         data={"count": "2"}).json()["job_id"]
    store.wait(job_id, timeout=5)
    sid = client.get(f"/api/jobs/{job_id}").json()["sources"][0]["source_id"]
    resp = client.post(f"/api/sources/{sid}/regenerate", data={"n": "2"})
    assert resp.status_code == 200
    assert resp.json()["delivered"] == 4  # 2 initial + 2 regenerated, all ok under FakeRunner
    assert client.post("/api/sources/nope/regenerate", data={"n": "1"}).status_code == 404


def test_cli_build_app_serves_health(tmp_path):
    from variant_maker.server.cli import build_app
    client = TestClient(build_app(str(tmp_path)))
    assert client.get("/api/health").json() == {"status": "ok"}
