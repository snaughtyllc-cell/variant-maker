"""Invited emails can paste a Drive folder link — not just the site admin."""
from __future__ import annotations

import json

from farm_fakes import FakeDrive
from fastapi.testclient import TestClient

from tests.server.fakes import FakeRunner
from tests.server.test_auth_app import ADMIN, _password_login
from variant_maker.server.app import create_app
from variant_maker.server.drive_config import ENV_OAUTH_CLIENT_ID, ENV_OAUTH_CLIENT_SECRET
from variant_maker.server.jobs import JobStore
from variant_maker.server.tenants import ADMIN_EMAIL_ENV
from variant_maker.server.workspace import Workspace

# Partner inbox from the lockout report, plus other invited shapes.
INVITED_EMAILS = (
    "richardsjaden99@gmail.com",
    "ops@agency.test",
    "va@agency.test",
)


def _env() -> dict[str, str]:
    return {
        ADMIN_EMAIL_ENV: ADMIN,
        "VARIANT_AUTH_SECRET": "test-auth-secret",
        ENV_OAUTH_CLIENT_ID: "test-client-id",
        ENV_OAUTH_CLIENT_SECRET: "test-client-secret",
    }


def _drive_app(tmp_path):
    drive = FakeDrive()
    sa = tmp_path / "sa.json"
    sa.write_text(json.dumps({"client_email": "studio@varimo.io"}))
    ws = Workspace(str(tmp_path))
    store = JobStore(ws, FakeRunner({}))
    env = _env()
    app = create_app(
        store,
        drive=drive,
        sa_json_path=str(sa),
        hydrate=True,
        auth_environ=env,
        oauth_environ=env,
    )
    return app, drive


def _attach_drive(app, drive: FakeDrive, workspace_id: str) -> None:
    app.state.drive = drive
    app.state.tenant_hub.bundle(workspace_id).drive = drive


def test_every_invited_email_can_paste_a_folder_link(tmp_path):
    app, drive = _drive_app(tmp_path)
    jeff = TestClient(app)
    assert _password_login(jeff, ADMIN, "secret12").status_code == 200
    jeff_ws = jeff.get("/api/auth/me").json()["workspace_id"]
    _attach_drive(app, drive, jeff_ws)

    folder = drive.make_folder("shared")
    url = f"https://drive.google.com/drive/folders/{folder}"

    admin_add = jeff.post("/api/drive/destinations", json={"name": "Jeff NC", "folder_url": url})
    assert admin_add.status_code == 201, admin_add.text

    for i, email in enumerate(INVITED_EMAILS):
        inv = jeff.post("/api/auth/invites", json={"email": email, "kind": "new_workspace"})
        assert inv.status_code == 201, inv.text
        client = TestClient(app)
        first = _password_login(client, email, f"secret12{i}")
        assert first.status_code == 200, first.text
        me = client.get("/api/auth/me").json()
        assert me["email"] == email
        assert me["is_admin"] is False
        _attach_drive(app, drive, me["workspace_id"])

        status = client.get("/api/drive/status").json()
        assert status["status"] == "ready", (email, status)

        listed = client.get("/api/drive/destinations").json()
        assert listed == [], email

        added = client.post(
            "/api/drive/destinations",
            json={"name": f"{email} reels", "folder_url": url},
        )
        assert added.status_code == 201, (email, added.text)
        assert added.json()["folder_id"] == folder

        file_link = client.post(
            "/api/drive/destinations",
            json={
                "name": "clip",
                "folder_url": "https://drive.google.com/file/d/1notafolderidxxx/view",
            },
        )
        assert file_link.status_code == 400, email
        assert "folder" in file_link.json()["detail"].lower()


def test_join_invite_can_paste_on_the_shared_workspace(tmp_path):
    app, drive = _drive_app(tmp_path)
    jeff = TestClient(app)
    assert _password_login(jeff, ADMIN, "secret12").status_code == 200
    jeff_ws = jeff.get("/api/auth/me").json()["workspace_id"]
    _attach_drive(app, drive, jeff_ws)
    folder = drive.make_folder("shared")
    url = f"https://drive.google.com/drive/folders/{folder}"
    assert jeff.post(
        "/api/drive/destinations", json={"name": "Jeff NC", "folder_url": url},
    ).status_code == 201

    inv = jeff.post(
        "/api/auth/invites",
        json={"email": "richardsjaden99@gmail.com", "kind": "join"},
    )
    assert inv.status_code == 201
    partner = TestClient(app)
    assert _password_login(partner, "richardsjaden99@gmail.com", "partner12").status_code == 200
    me = partner.get("/api/auth/me").json()
    assert me["workspace_id"] == jeff_ws
    _attach_drive(app, drive, me["workspace_id"])

    existing = partner.get("/api/drive/destinations").json()
    assert [d["name"] for d in existing] == ["Jeff NC"]
    added = partner.post(
        "/api/drive/destinations",
        json={"name": "Partner folder", "folder_url": url},
    )
    assert added.status_code == 201, added.text
    names = [d["name"] for d in partner.get("/api/drive/destinations").json()]
    assert names == ["Jeff NC", "Partner folder"]
