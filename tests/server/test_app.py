import json
import zipfile

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


def test_create_job_quality_mode_hq(tmp_path):
    client, store = _client(tmp_path)
    resp = client.post(
        "/api/jobs",
        files=[("files", ("a.mp4", b"x", "video/mp4"))],
        data={"count": "1", "quality_mode": "hq"},
    )
    assert resp.status_code == 201
    store.wait(resp.json()["job_id"], timeout=5)
    assert store._runner.last_quality_mode == "hq"


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


def test_events_snapshot_returns_json_log(tmp_path):
    client, store = _client(tmp_path)
    job_id = client.post("/api/jobs",
                         files=[("files", ("a.mp4", b"x", "video/mp4"))],
                         data={"count": "2"}).json()["job_id"]
    store.wait(job_id, timeout=5)
    snap = client.get(f"/api/jobs/{job_id}/events-snapshot").json()
    assert snap["job_id"] == job_id
    assert snap["state"] == "done"
    states = [e.get("state") for e in snap["events"]]
    assert states.count("done") == 2
    assert "rendering" in states


def test_chunked_upload_then_create_job(tmp_path):
    client, store = _client(tmp_path)
    payload = b"fake-video-bytes-" * 1000
    init = client.post(
        "/api/uploads",
        data={"filename": "clip.mp4", "size": str(len(payload))},
    )
    assert init.status_code == 200
    upload_id = init.json()["upload_id"]
    mid = len(payload) // 2
    r1 = client.put(f"/api/uploads/{upload_id}?offset=0", content=payload[:mid])
    r2 = client.put(f"/api/uploads/{upload_id}?offset={mid}", content=payload[mid:])
    assert r1.status_code == 200 and r2.status_code == 200
    job = client.post(
        "/api/jobs/from-uploads",
        data={"upload_ids": upload_id, "count": "1", "allow_creative_escalate": "true"},
    )
    assert job.status_code == 201
    body = job.json()
    assert body["sources"][0]["filename"] == "clip.mp4"
    store.wait(body["job_id"], timeout=5)


def test_get_job_exposes_in_flight_from_event_log(tmp_path):
    from variant_maker.server.events import VariantEvent

    client, store = _client(tmp_path)
    job_id = client.post("/api/jobs",
                         files=[("files", ("a.mp4", b"x", "video/mp4"))],
                         data={"count": "1"}).json()["job_id"]
    store.wait(job_id, timeout=5)
    job = store.get(job_id)
    assert job is not None
    job.state = "running"
    sid = job.sources[0].source_id
    job.events.append(VariantEvent(source_id=sid, index=2, state="uniqueness"))
    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["sources"][0]["in_flight"] == {
        "index": 2, "state": "uniqueness", "attempt": 0, "max_attempts": 0,
    }


def test_done_job_does_not_keep_rendering_in_flight(tmp_path):
    from variant_maker.server.events import VariantEvent

    client, store = _client(tmp_path)
    job_id = client.post("/api/jobs",
                         files=[("files", ("a.mp4", b"x", "video/mp4"))],
                         data={"count": "1"}).json()["job_id"]
    store.wait(job_id, timeout=5)
    job = store.get(job_id)
    assert job is not None
    sid = job.sources[0].source_id
    job.events.append(VariantEvent(source_id=sid, index=1, state="rendering"))
    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["state"] == "done"
    assert detail["sources"][0]["in_flight"] is None
    assert detail.get("error") in (None, "")


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
    assert gallery[0]["failed"] == 1
    assert gallery[0]["job_state"] == "done"
    assert all(v["status"] == "ok" for v in gallery[0]["variants"])
    assert gallery[0]["variants"][0]["uniqueness"] == 0.42


def test_diagnostics_lists_non_ok(tmp_path):
    client, store = _client(tmp_path, plan={2: "best_effort", 3: "best_effort"})
    job_id = client.post("/api/jobs",
                         files=[("files", ("a.mp4", b"x", "video/mp4"))],
                         data={"count": "3"}).json()["job_id"]
    store.wait(job_id, timeout=5)
    diag = client.get("/api/diagnostics").json()
    assert len(diag) == 2
    assert all(d["status"] == "best_effort" for d in diag)


def test_done_events_carry_uniqueness_fields(tmp_path):
    client, store = _client(tmp_path)
    job_id = client.post("/api/jobs",
                         files=[("files", ("a.mp4", b"x", "video/mp4"))],
                         data={"count": "1"}).json()["job_id"]
    store.wait(job_id, timeout=5)
    snap = client.get(f"/api/jobs/{job_id}/events-snapshot").json()
    done = [e for e in snap["events"] if e.get("state") == "done"]
    assert len(done) == 1
    assert done[0]["uniqueness"] == 0.42
    assert done[0]["uniqueness_status"] == "ok"
    assert done[0]["uniqueness_metric"] == "ssim_bits_v1"
    assert done[0]["uniqueness_target"] == 24 / 64


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


def test_get_job_detail_includes_uniqueness_fields(tmp_path):
    client, store = _client(tmp_path)
    job_id = client.post("/api/jobs",
                         files=[("files", ("a.mp4", b"x", "video/mp4"))],
                         data={"count": "1"}).json()["job_id"]
    store.wait(job_id, timeout=5)
    v = client.get(f"/api/jobs/{job_id}").json()["sources"][0]["variants"][0]
    assert v["uniqueness"] == 0.42
    assert v["uniqueness_status"] == "ok"
    assert v["uniqueness_metric"] == "ssim_bits_v1"
    assert v["uniqueness_target"] == 24 / 64
    assert v["preset_used"] == "medium"
    assert v["strength_final"] == 1.0
    assert v["escalated"] is False
    assert v["platform_result"] is None


def test_platform_result_roundtrip(tmp_path):
    client, store = _client(tmp_path)
    job_id = client.post("/api/jobs",
                         files=[("files", ("a.mp4", b"x", "video/mp4"))],
                         data={"count": "1"}).json()["job_id"]
    store.wait(job_id, timeout=5)
    src = client.get(f"/api/jobs/{job_id}").json()["sources"][0]
    sid = src["source_id"]
    index = src["variants"][0]["index"]

    resp = client.post(f"/api/variants/{sid}/{index}/platform-result",
                       json={"result": "passed"})
    assert resp.status_code == 200
    assert resp.json()["platform_result"] == "passed"

    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["sources"][0]["variants"][0]["platform_result"] == "passed"

    assert client.post(f"/api/variants/{sid}/999/platform-result",
                       json={"result": "passed"}).status_code == 404
    assert client.post(f"/api/variants/nope/{index}/platform-result",
                       json={"result": "passed"}).status_code == 404
    assert client.post(f"/api/variants/{sid}/{index}/platform-result",
                       json={"result": "bogus"}).status_code == 422


def test_zip_contains_ok_variants(tmp_path):
    client, store = _client(tmp_path, plan={2: "best_effort"})
    job_id = client.post("/api/jobs",
                         files=[("files", ("a.mp4", b"x", "video/mp4"))],
                         data={"count": "3"}).json()["job_id"]
    store.wait(job_id, timeout=5)
    src = client.get(f"/api/jobs/{job_id}").json()["sources"][0]
    sid = src["source_id"]
    ok_filenames = {v["filename"] for v in src["variants"]}

    resp = client.get(f"/api/sources/{sid}/zip")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"

    import io
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    assert set(zf.namelist()) == ok_filenames

    assert client.get("/api/sources/nope/zip").status_code == 404


def test_cli_build_app_serves_health(tmp_path):
    from variant_maker.server.cli import build_app
    client = TestClient(build_app(str(tmp_path)))
    assert client.get("/api/health").json() == {"status": "ok"}


def test_make_runner_local():
    from variant_maker.server.cli import make_runner
    from variant_maker.server.runner import LocalRunner
    assert isinstance(make_runner("local"), LocalRunner)


def test_make_runner_runpod_from_env(monkeypatch):
    from variant_maker.server import cli
    from variant_maker.server.runpod_runner import RunPodServerlessRunner
    # avoid real boto3/httpx construction
    monkeypatch.setattr(cli, "S3ObjectStore", lambda **kw: object())
    monkeypatch.setattr(cli, "HttpRunPodClient", lambda **kw: object())
    for k, v in {"RUNPOD_ENDPOINT_ID": "ep", "RUNPOD_API_KEY": "k",
                 "R2_ENDPOINT": "https://r2", "R2_BUCKET": "b",
                 "R2_ACCESS_KEY": "a", "R2_SECRET_KEY": "s"}.items():
        monkeypatch.setenv(k, v)
    assert isinstance(cli.make_runner("runpod"), RunPodServerlessRunner)


def test_make_runner_runpod_missing_env_exits(monkeypatch):
    from variant_maker.server import cli
    for k in ("RUNPOD_ENDPOINT_ID", "RUNPOD_API_KEY", "R2_ENDPOINT", "R2_BUCKET",
              "R2_ACCESS_KEY", "R2_SECRET_KEY"):
        monkeypatch.delenv(k, raising=False)
    import pytest
    with pytest.raises(SystemExit):
        cli.make_runner("runpod")


def test_resolve_runner_auto_runpod_when_env_complete(monkeypatch):
    from variant_maker.server import cli
    for k, v in {"RUNPOD_ENDPOINT_ID": "ep", "RUNPOD_API_KEY": "k",
                 "R2_ENDPOINT": "https://r2", "R2_BUCKET": "b",
                 "R2_ACCESS_KEY": "a", "R2_SECRET_KEY": "s"}.items():
        monkeypatch.setenv(k, v)
    assert cli.resolve_runner(None) == "runpod"


def test_resolve_runner_auto_local_when_env_incomplete(monkeypatch):
    from variant_maker.server import cli
    for k in ("RUNPOD_ENDPOINT_ID", "RUNPOD_API_KEY", "R2_ENDPOINT", "R2_BUCKET",
              "R2_ACCESS_KEY", "R2_SECRET_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert cli.resolve_runner(None) == "local"
    assert cli.resolve_runner("runpod") == "runpod"
