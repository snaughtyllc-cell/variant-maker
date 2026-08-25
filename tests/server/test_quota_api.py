"""Creator Fast/HQ caps on generate. Auth-on Studio only."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from tests.server.test_auth_app import _auth_app, _login, _tenant_wait


def test_new_workspace_is_creator_with_fast_quota(tmp_path):
    app, _ = _auth_app(tmp_path)
    jeff = TestClient(app)
    ops = TestClient(app)
    _login(jeff, "jeff")
    jeff_me = jeff.get("/api/auth/me").json()
    assert jeff_me["plan"] == "internal"
    assert jeff_me["quota"]["fast_limit"] is None

    jeff.post("/api/auth/invites", json={"email": "ops@x.com", "kind": "new_workspace"})
    _login(ops, "ops")
    me = ops.get("/api/auth/me").json()
    assert me["plan"] == "creator"
    assert me["quota"]["fast_limit"] == 200
    assert me["quota"]["fast_used"] == 0
    assert me["quota"]["hq_limit"] == 0
    spaces = jeff.get("/api/admin/workspaces").json()
    row = next(s for s in spaces if s["id"] == me["workspace_id"])
    assert row["plan"] == "creator"


def test_creator_fast_cap_returns_429_with_human_sentence(tmp_path):
    app, _ = _auth_app(tmp_path)
    jeff = TestClient(app)
    ops = TestClient(app)
    _login(jeff, "jeff")
    jeff.post("/api/auth/invites", json={"email": "ops@x.com", "kind": "new_workspace"})
    _login(ops, "ops")
    ws_id = ops.get("/api/auth/me").json()["workspace_id"]
    path = tmp_path / "auth" / "tenants.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["workspaces"][ws_id]["fast_limit_30d"] = 1
    path.write_text(json.dumps(data), encoding="utf-8")

    first = ops.post(
        "/api/jobs",
        files=[("files", ("a.mp4", b"x", "video/mp4"))],
        data={"count": "1"},
    )
    assert first.status_code == 201
    _tenant_wait(ops, first.json()["job_id"])
    used = ops.get("/api/auth/me").json()["quota"]["fast_used"]
    assert used == 1

    blocked = ops.post(
        "/api/jobs",
        files=[("files", ("b.mp4", b"y", "video/mp4"))],
        data={"count": "1"},
    )
    assert blocked.status_code == 429
    detail = blocked.json()["detail"]
    assert "1 / 1" in detail
    assert "Jeff" in detail


def test_creator_hq_is_off(tmp_path):
    app, _ = _auth_app(tmp_path)
    jeff = TestClient(app)
    ops = TestClient(app)
    _login(jeff, "jeff")
    jeff.post("/api/auth/invites", json={"email": "ops@x.com", "kind": "new_workspace"})
    _login(ops, "ops")
    blocked = ops.post(
        "/api/jobs",
        files=[("files", ("a.mp4", b"x", "video/mp4"))],
        data={"count": "1", "quality_mode": "hq"},
    )
    assert blocked.status_code == 429
    assert "HQ is not on this plan" in blocked.json()["detail"]


def test_creator_cannot_open_team_or_workflows(tmp_path):
    app, _ = _auth_app(tmp_path)
    jeff = TestClient(app)
    ops = TestClient(app)
    _login(jeff, "jeff")
    jeff.post("/api/auth/invites", json={"email": "ops@x.com", "kind": "new_workspace"})
    _login(ops, "ops")
    team = ops.get("/api/workspace/team")
    assert team.status_code == 403
    assert "Pro" in team.json()["detail"]
    flows = ops.get("/api/workflows")
    assert flows.status_code == 403


def test_admin_can_bump_plan_to_pro(tmp_path):
    app, _ = _auth_app(tmp_path)
    jeff = TestClient(app)
    ops = TestClient(app)
    _login(jeff, "jeff")
    jeff.post("/api/auth/invites", json={"email": "ops@x.com", "kind": "new_workspace"})
    _login(ops, "ops")
    ws_id = ops.get("/api/auth/me").json()["workspace_id"]
    patched = jeff.patch(
        f"/api/admin/workspaces/{ws_id}", json={"plan": "pro"},
    )
    assert patched.status_code == 200
    assert patched.json()["plan"] == "pro"
    me = ops.get("/api/auth/me").json()
    assert me["plan"] == "pro"
    assert me["quota"]["fast_limit"] == 1000
    assert ops.get("/api/workspace/team").status_code == 200
    assert ops.get("/api/workflows").status_code == 200
