"""Public /api/v1 + cookie API-key management."""
from __future__ import annotations

import json

from farm_fakes import FakeDrive
from fastapi.testclient import TestClient

from tests.server.fakes import FakeRunner
from tests.server.test_auth_app import _env, _exchange, _login, _tenant_wait
from variant_maker.server.app import create_app
from variant_maker.server.jobs import JobStore
from variant_maker.server.workspace import Workspace

UNSAFE = ("quality", "uniqueness", "look_mae", "sha256", "vmaf", "file_url")


def _v1_app(tmp_path, *, drive=None):
    ws = Workspace(str(tmp_path))
    store = JobStore(ws, FakeRunner({}))
    env = _env()
    sa_path = tmp_path / "sa.json"
    sa_path.write_text(json.dumps({"client_email": "bot@x.iam.gserviceaccount.com"}))
    drive = drive or FakeDrive()
    app = create_app(
        store,
        hydrate=True,
        auth_environ=env,
        oauth_environ=env,
        login_exchange=_exchange,
        sa_json_path=str(sa_path),
        drive=drive,
    )
    return app, store, drive


def _headers(token: str, **extra):
    headers = {"Authorization": f"Bearer {token}"}
    headers.update(extra)
    return headers


def _dest(client: TestClient, drive: FakeDrive, name="Inbox"):
    folder = drive.make_folder(name)
    resp = client.post("/api/drive/destinations", json={"name": name, "folder_url": folder})
    assert resp.status_code == 201, resp.text
    return resp.json(), folder


def _issue(client: TestClient, *, preset="full", label="Agency bot"):
    resp = client.post(
        "/api/workspace/api-keys",
        json={"label": label, "preset": preset, "expires_days": 30},
    )
    assert resp.status_code == 201, resp.text
    assert resp.headers.get("cache-control") == "no-store"
    body = resp.json()
    assert body["token"].startswith("vf_")
    return body


def test_auth_off_disables_keys_and_bearer(tmp_path):
    client = TestClient(create_app(JobStore(Workspace(str(tmp_path)), FakeRunner({}))))
    assert client.post("/api/workspace/api-keys", json={"label": "x", "preset": "read"}).status_code == 404
    assert client.get("/api/v1/gallery").status_code == 401
    assert client.get("/api/gallery").status_code == 200


def test_owner_issues_key_va_and_viewing_admin_cannot(tmp_path):
    app, _, _ = _v1_app(tmp_path)
    jeff = TestClient(app)
    va = TestClient(app)
    ops = TestClient(app)
    _login(jeff, "jeff")
    created = _issue(jeff)
    listed = jeff.get("/api/workspace/api-keys").json()
    assert listed["keys"][0]["prefix"] == created["prefix"]
    assert "token" not in listed["keys"][0]
    assert listed["keys"][0]["key_id"] == created["key_id"]

    jeff.post("/api/auth/invites", json={"email": "va@x.com", "kind": "join"})
    _login(va, "va")
    assert va.post(
        "/api/workspace/api-keys", json={"label": "nope", "preset": "read"},
    ).status_code == 403

    jeff.post("/api/auth/invites", json={"email": "ops@x.com", "kind": "new_workspace"})
    _login(ops, "ops")
    ops_id = ops.get("/api/auth/me").json()["workspace_id"]
    assert jeff.post("/api/admin/view", json={"workspace_id": ops_id}).status_code == 204
    assert jeff.get("/api/workspace/api-keys").status_code == 403
    assert jeff.post(
        "/api/workspace/api-keys", json={"label": "nope", "preset": "read"},
    ).status_code == 403


def test_bearer_is_not_a_session_and_cookie_is_not_v1(tmp_path):
    app, _, _ = _v1_app(tmp_path)
    jeff = TestClient(app)
    _login(jeff, "jeff")
    token = _issue(jeff)["token"]

    assert jeff.get("/api/v1/gallery").status_code == 401
    anon = TestClient(app)
    assert anon.get("/api/gallery", headers=_headers(token)).status_code == 401
    bad = TestClient(app)
    bad.cookies.update(jeff.cookies)
    assert bad.get(
        "/api/v1/gallery",
        headers=_headers("vf_deadbeefdeadbee_aa" + "b" * 62),
    ).status_code == 401
    assert bad.get("/api/gallery").status_code == 200


def test_pack_gallery_export_loop_and_safe_projection(tmp_path):
    drive = FakeDrive()
    app, _store, drive = _v1_app(tmp_path, drive=drive)
    jeff = TestClient(app)
    _login(jeff, "jeff")
    dest_in, inbox = _dest(jeff, drive, "Inbox")
    dest_out, _outbox = _dest(jeff, drive, "Out")
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video-bytes")
    fid = drive.put_file("clip.mp4", str(clip), parent=inbox)
    token = _issue(jeff)["token"]
    api = TestClient(app)

    created = api.post(
        "/api/v1/packs",
        headers=_headers(token, **{"Idempotency-Key": "pack-1"}),
        json={"input_destination_id": dest_in["id"], "drive_file_id": fid, "count": 8},
    )
    assert created.status_code == 201, created.text
    pack_id = created.json()["pack_id"]
    assert created.json()["status_url"] == f"/api/v1/packs/{pack_id}"
    replay = api.post(
        "/api/v1/packs",
        headers=_headers(token, **{"Idempotency-Key": "pack-1"}),
        json={"input_destination_id": dest_in["id"], "drive_file_id": fid, "count": 8},
    )
    assert replay.status_code == 201
    assert replay.json()["pack_id"] == pack_id

    _tenant_wait(jeff, pack_id)
    got = api.get(f"/api/v1/packs/{pack_id}", headers=_headers(token))
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["state"] == "done"
    assert body["requested"] == 8
    assert body["ready"] == 8
    assert body["review_url"] == "/gallery"
    blob = json.dumps(body)
    for word in UNSAFE:
        assert word not in blob
    copy = body["sources"][0]["copies"][0]

    gallery = api.get("/api/v1/gallery", headers=_headers(token)).json()
    assert gallery["items"][0]["pack_id"] == pack_id
    assert "quality" not in json.dumps(gallery)

    exported = api.post(
        "/api/v1/drive/exports",
        headers=_headers(token, **{"Idempotency-Key": "exp-1"}),
        json={
            "destination_id": dest_out["id"],
            "variants": [{"source_id": body["sources"][0]["source_id"], "index": copy["index"]}],
        },
    )
    assert exported.status_code == 201, exported.text
    export_id = exported.json()["export_id"]
    status = api.get(f"/api/v1/drive/exports/{export_id}", headers=_headers(token))
    assert status.status_code == 200
    assert status.json()["export_id"] == export_id
    assert "local_path" not in json.dumps(status.json())

    ws_id = jeff.get("/api/auth/me").json()["workspace_id"]
    job = jeff.app.state.tenant_hub.bundle(ws_id).store.get(pack_id)
    assert job is not None
    assert job.quality_mode == "fast"
    assert job.prep_mode == "none"


def test_scopes_and_cross_workspace_404(tmp_path):
    drive = FakeDrive()
    app, _, drive = _v1_app(tmp_path, drive=drive)
    jeff = TestClient(app)
    ops = TestClient(app)
    _login(jeff, "jeff")
    jeff.post("/api/auth/invites", json={"email": "ops@x.com", "kind": "new_workspace"})
    _login(ops, "ops")
    dest, inbox = _dest(jeff, drive, "Inbox")
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"x")
    fid = drive.put_file("clip.mp4", str(clip), parent=inbox)
    full = _issue(jeff, preset="full")["token"]
    read = _issue(jeff, preset="read", label="reader")["token"]
    api = TestClient(app)

    assert api.post(
        "/api/v1/packs",
        headers=_headers(read, **{"Idempotency-Key": "nope"}),
        json={"input_destination_id": dest["id"], "drive_file_id": fid, "count": 8},
    ).status_code == 403

    created = api.post(
        "/api/v1/packs",
        headers=_headers(full, **{"Idempotency-Key": "pack-ops"}),
        json={"input_destination_id": dest["id"], "drive_file_id": fid, "count": 8},
    )
    assert created.status_code == 201
    pack_id = created.json()["pack_id"]
    ops_token = _issue(ops, label="ops bot")["token"]
    assert api.get(f"/api/v1/packs/{pack_id}", headers=_headers(ops_token)).status_code == 404
    assert api.post(
        "/api/workspace/api-keys",
        headers=_headers(full),
        json={"label": "from-key", "preset": "read"},
    ).status_code == 401


def test_revoke_blocks_next_request(tmp_path):
    app, _, _ = _v1_app(tmp_path)
    jeff = TestClient(app)
    _login(jeff, "jeff")
    created = _issue(jeff, preset="read")
    api = TestClient(app)
    assert api.get("/api/v1/gallery", headers=_headers(created["token"])).status_code == 200
    assert jeff.delete(f"/api/workspace/api-keys/{created['key_id']}").status_code == 204
    assert jeff.delete(f"/api/workspace/api-keys/{created['key_id']}").status_code == 204
    assert api.get("/api/v1/gallery", headers=_headers(created["token"])).status_code == 401


def test_count_and_missing_idempotency(tmp_path):
    drive = FakeDrive()
    app, _, drive = _v1_app(tmp_path, drive=drive)
    jeff = TestClient(app)
    _login(jeff, "jeff")
    dest, inbox = _dest(jeff, drive, "Inbox")
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"x")
    fid = drive.put_file("clip.mp4", str(clip), parent=inbox)
    token = _issue(jeff)["token"]
    api = TestClient(app)
    assert api.post(
        "/api/v1/packs",
        headers=_headers(token, **{"Idempotency-Key": "c"}),
        json={"input_destination_id": dest["id"], "drive_file_id": fid, "count": 3},
    ).status_code == 400
    assert api.post(
        "/api/v1/packs",
        headers=_headers(token),
        json={"input_destination_id": dest["id"], "drive_file_id": fid, "count": 8},
    ).status_code == 400


def test_openapi_is_public_and_has_no_cookie_routes(tmp_path):
    app, _, _ = _v1_app(tmp_path)
    anon = TestClient(app)
    spec = anon.get("/api/v1/openapi.json")
    assert spec.status_code == 200
    paths = spec.json()["paths"]
    assert "/packs" in paths
    assert "/api/jobs" not in json.dumps(paths)
    assert "/gallery" in paths
