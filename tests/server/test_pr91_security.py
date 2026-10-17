"""Regression probes for the PR #91 security boundary."""

import asyncio
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from tests.server.fakes import FakeObjectStore, FakeRunner
from tests.server.test_auth_app import ADMIN, _auth_app, _login, _tenant_wait
from variant_maker.server.app import create_app
from variant_maker.server.jobs import JobStore
from variant_maker.server.workspace import Workspace


def test_chunk_limit_stops_receiving_before_buffering_whole_body(tmp_path, monkeypatch):
    import variant_maker.server.app as module

    monkeypatch.setattr(module, "_MAX_UPLOAD_BYTES", 4)
    app = create_app(JobStore(Workspace(str(tmp_path)), FakeRunner({})))
    client = TestClient(app)
    uid = client.post("/api/uploads", data={"filename": "x.mp4", "size": 4}).json()["upload_id"]
    endpoint = next(r.endpoint for r in app.routes if r.path == "/api/uploads/{upload_id}")
    received = []

    async def receive():
        received.append(1)
        return {"type": "http.request", "body": b"xxx", "more_body": len(received) < 3}

    request = Request({"type": "http", "method": "PUT", "path": "/", "headers": []}, receive)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(uid, request, offset=0))
    assert exc.value.status_code == 413
    assert len(received) == 2, "must reject at the first overflowing chunk, without draining body"
    assert (tmp_path / "uploads" / uid / "x.mp4").stat().st_size <= 4


def test_direct_upload_binds_size_in_real_s3_signature(tmp_path, monkeypatch):
    import boto3
    from botocore.config import Config

    from variant_maker.server import storage

    s3 = boto3.client(
        "s3",
        endpoint_url="https://objects.test",
        region_name="auto",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        config=Config(signature_version="s3v4"),
    )
    monkeypatch.setattr(storage, "_make_client", lambda **kw: s3)
    blob = storage.S3ObjectStore(
        endpoint_url="https://objects.test", bucket="b", access_key="test", secret_key="test"
    )
    client = TestClient(
        create_app(JobStore(Workspace(str(tmp_path)), FakeRunner({}), object_store=blob))
    )
    init = client.post("/api/uploads/direct", data={"filename": "x.mp4", "size": 4}).json()
    signed = parse_qs(urlparse(init["url"]).query)["X-Amz-SignedHeaders"][0].split(";")
    assert "content-length" in signed


def test_direct_object_rejects_oversize_before_copy(tmp_path, monkeypatch):
    import variant_maker.server.app as module

    monkeypatch.setattr(module, "_MAX_UPLOAD_BYTES", 4)
    blob = FakeObjectStore()
    store = JobStore(Workspace(str(tmp_path)), FakeRunner({}), object_store=blob)
    client = TestClient(create_app(store))
    key = client.post("/api/uploads/direct", data={"filename": "x.mp4", "size": 4}).json()["key"]
    blob.put_bytes(key, b"oversized")
    response = client.post(
        "/api/jobs/from-object", json={"items": [{"filename": "x.mp4", "key": key}], "count": 1}
    )
    assert response.status_code == 413
    assert blob.list_prefix("inputs/") == []
    assert store.list() == []


def test_launcher_preserves_tcp_peer_for_login_throttle(tmp_path, monkeypatch):
    import uvicorn

    from variant_maker.server import cli
    from variant_maker.server.login_limit import MAX_FAILURES, reset

    reset()
    app, _ = _auth_app(tmp_path)
    captured = {}
    monkeypatch.setattr(cli, "build_app", lambda *a: app)
    monkeypatch.setattr("sys.argv", ["variant-server", "--data-dir", str(tmp_path)])
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: captured.update(app=app, **kw))
    with pytest.raises(SystemExit):
        cli.main()
    config = uvicorn.Config(**captured)
    config.load()

    async def probe():
        transport = httpx.ASGITransport(app=config.loaded_app, client=("127.0.0.1", 50000))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            assert (
                await client.post(
                    "/api/auth/password", json={"email": ADMIN, "password": "secret12"}
                )
            ).status_code == 200
            for i in range(MAX_FAILURES):
                assert (
                    await client.post(
                        "/api/auth/password",
                        json={"email": ADMIN, "password": "wrong-pass"},
                        headers={"X-Forwarded-For": f"198.51.100.{i + 1}"},
                    )
                ).status_code == 401
            response = await client.post(
                "/api/auth/password",
                json={"email": ADMIN, "password": "wrong-pass"},
                headers={"X-Forwarded-For": "203.0.113.99"},
            )
            assert response.status_code == 429

    try:
        asyncio.run(probe())
    finally:
        reset()


def test_member_cannot_read_insights_via_gallery_job_or_mutation(tmp_path):
    app, _ = _auth_app(tmp_path)
    owner, member = TestClient(app), TestClient(app)
    _login(owner, "jeff")
    owner.post("/api/auth/invites", json={"email": "va@x.com", "kind": "join"})
    _login(member, "va")
    created = owner.post(
        "/api/jobs", files=[("files", ("x.mp4", b"x", "video/mp4"))], data={"count": 1}
    ).json()
    jid = created["job_id"]
    _tenant_wait(owner, jid)
    sid = created["sources"][0]["source_id"]
    wsid = owner.get("/api/auth/me").json()["workspace_id"]
    store = app.state.tenant_hub.bundle(wsid).store
    store.set_ig_insights(
        sid,
        1,
        ig_media_id="private-media",
        ig_user_id="private-account",
        insights={"views": 1234, "reach": 999},
    )
    assert owner.get("/api/gallery").json()[0]["insights_views"] == 1234
    for source in (
        member.get("/api/gallery").json()[0],
        member.get(f"/api/jobs/{jid}").json()["sources"][0],
        member.post(f"/api/jobs/{jid}/cancel").json()["sources"][0],
    ):
        assert source["insights_views"] is None
        assert source["variants"][0]["ig_insights"] is None
    variant = member.post(f"/api/variants/{sid}/1/caption", json={"caption": "Updated"}).json()
    assert variant["ig_insights"] is None
    assert variant["ig_user_id"] is None
    assert owner.get("/api/gallery").json()[0]["insights_views"] == 1234


@pytest.mark.parametrize(
    "route,key_name",
    [
        ("/api/variants/{sid}/v01.mp4", "v01.mp4"),
        ("/api/look/{sid}/look_v01.jpg", "look_v01.jpg"),
        ("/api/sources/{sid}/zip", "variants.zip"),
    ],
)
def test_shared_object_downloads_require_tenant_source(tmp_path, route, key_name):
    app, _ = _auth_app(tmp_path)
    blob = FakeObjectStore()
    app.state.tenant_hub._object_store = blob
    owner, other = TestClient(app), TestClient(app)
    _login(owner, "jeff")
    owner.post("/api/auth/invites", json={"email": "ops@x.com", "kind": "new_workspace"})
    _login(other, "ops")
    created = owner.post(
        "/api/jobs", files=[("files", ("x.mp4", b"x", "video/mp4"))], data={"count": 1}
    ).json()
    _tenant_wait(owner, created["job_id"])
    sid = created["sources"][0]["source_id"]
    blob.put_bytes(f"outputs/{sid}/{key_name}", b"private media")
    url = route.format(sid=sid)
    assert owner.get(url, follow_redirects=False).status_code in (200, 302)
    signed_before = len(blob.presigns)
    response = other.get(url, follow_redirects=False)
    assert response.status_code == 404
    assert len(blob.presigns) == signed_before


def test_usage_actor_ignores_client_email_and_stays_out_of_job_response(tmp_path):
    app, _ = _auth_app(tmp_path)
    owner, member = TestClient(app), TestClient(app)
    _login(owner, "jeff")
    owner.post("/api/auth/invites", json={"email": "va@x.com", "kind": "join"})
    _login(member, "va")
    created = member.post(
        "/api/jobs",
        files=[("files", ("x.mp4", b"x", "video/mp4"))],
        data={"count": 1, "actor_email": ADMIN, "customer_email": ADMIN},
    ).json()
    _tenant_wait(member, created["job_id"])
    wsid = member.get("/api/auth/me").json()["workspace_id"]
    job = app.state.tenant_hub.bundle(wsid).store.get(created["job_id"])
    assert job.telemetry["customer_email"] == "va@x.com"
    assert "customer_email" not in member.get(f"/api/jobs/{job.job_id}").text
    assert member.get("/api/workspace/team").status_code == 403


def test_direct_upload_is_tenant_owned_and_consumed_once(tmp_path):
    app, _ = _auth_app(tmp_path)
    blob = FakeObjectStore()
    app.state.tenant_hub._object_store = blob
    owner, other = TestClient(app), TestClient(app)
    _login(owner, "jeff")
    owner.post("/api/auth/invites", json={"email": "ops@x.com", "kind": "new_workspace"})
    _login(other, "ops")
    key = owner.post("/api/uploads/direct", data={"filename": "x.mp4", "size": 4}).json()["key"]
    blob.put_bytes(key, b"xxxx")
    payload = {"items": [{"filename": "x.mp4", "key": key}], "count": 1}
    assert other.post("/api/jobs/from-object", json=payload).status_code == 404
    created = owner.post("/api/jobs/from-object", json=payload)
    assert created.status_code == 201
    _tenant_wait(owner, created.json()["job_id"])
    assert owner.post("/api/jobs/from-object", json=payload).status_code == 404
    for key in ("inputs/other/x.mp4", "outputs/other/v01.mp4"):
        payload["items"][0]["key"] = key
        assert owner.post("/api/jobs/from-object", json=payload).status_code == 400


def test_signed_cookie_truncation_and_member_view_cookie(tmp_path):
    from tests.server.test_auth_app import SECRET
    from variant_maker.server.sessions import COOKIE_NAME, VIEW_COOKIE_NAME, sign_view

    app, _ = _auth_app(tmp_path)
    owner, other = TestClient(app), TestClient(app)
    _login(owner, "jeff")
    owner.post("/api/auth/invites", json={"email": "ops@x.com", "kind": "new_workspace"})
    _login(other, "ops")
    home = other.get("/api/auth/me").json()["workspace_id"]
    owner_ws = owner.get("/api/auth/me").json()["workspace_id"]
    other.cookies.set(VIEW_COOKIE_NAME, sign_view(owner_ws, SECRET))
    assert other.get("/api/auth/me").json()["workspace_id"] == home
    signed = owner.cookies.get(COOKIE_NAME)
    owner.cookies.clear()
    owner.cookies.set(COOKIE_NAME, signed[:-1])
    assert owner.get("/api/gallery").status_code == 401
