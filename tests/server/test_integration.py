import pytest
from fastapi.testclient import TestClient

from variant_maker.server.app import create_app
from variant_maker.server.jobs import JobStore
from variant_maker.server.runner import LocalRunner
from variant_maker.server.workspace import Workspace


@pytest.mark.integration
def test_end_to_end_real_engine(tmp_path, real_clip):
    store = JobStore(Workspace(str(tmp_path)), LocalRunner())
    client = TestClient(create_app(store))

    with open(real_clip, "rb") as f:
        data = f.read()
    job_id = client.post(
        "/api/jobs",
        files=[("files", ("clip.mp4", data, "video/mp4"))],
        data={"count": "2"},
    ).json()["job_id"]

    assert store.wait(job_id, timeout=300)
    detail = client.get(f"/api/jobs/{job_id}").json()
    src = detail["sources"][0]
    assert src["requested"] == 2
    # at least one variant delivered, and its file is served
    assert src["delivered"] >= 1
    fname = src["variants"][0]["filename"]
    sid = src["source_id"]
    r = client.get(f"/api/variants/{sid}/{fname}")
    assert r.status_code == 200 and len(r.content) > 0

    gallery = client.get("/api/gallery").json()
    assert any(s["source_id"] == sid for s in gallery)
