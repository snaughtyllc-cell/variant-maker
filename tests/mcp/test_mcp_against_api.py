"""MCP HTTP client against the real /api/v1 adapters."""
from __future__ import annotations

import httpx
from farm_fakes import FakeDrive
from fastapi.testclient import TestClient

from tests.server.test_api_v1 import _dest, _issue, _login, _v1_app
from variant_maker.mcp.client import StudioV1Client


class _StarletteTransport(httpx.BaseTransport):
    """Sync httpx transport over Starlette TestClient (ASGITransport is async-only)."""

    def __init__(self, app) -> None:
        self._app = TestClient(app)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.url.query:
            path = f"{path}?{request.url.query.decode()}"
        response = self._app.request(
            request.method,
            path,
            headers=dict(request.headers),
            content=request.content,
        )
        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=response.content,
        )


def test_mcp_client_create_pack_hits_v1(tmp_path):
    drive = FakeDrive()
    app, _, drive = _v1_app(tmp_path, drive=drive)
    jeff = TestClient(app)
    _login(jeff, "jeff")
    dest, inbox = _dest(jeff, drive, "Inbox")
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video-bytes")
    fid = drive.put_file("clip.mp4", str(clip), parent=inbox)
    token = _issue(jeff)["token"]
    client = StudioV1Client(
        base_url="https://studio.example",
        api_key=token,
        transport=_StarletteTransport(app),
    )
    inbox_id = next(f["id"] for f in client.list_folders()["folders"] if f["name"] == "Inbox")
    clip_id = next(c["id"] for c in client.list_clips(inbox_id)["clips"] if c["name"] == "clip.mp4")
    assert inbox_id == dest["id"]
    assert clip_id == fid
    created = client.create_pack(
        input_destination_id=inbox_id,
        drive_file_id=clip_id,
        count=8,
        request_id="mcp-pack-1",
    )
    assert created["pack_id"]
    assert created["state"] == "running"
    gallery = client.list_gallery(pack_id=created["pack_id"])
    assert gallery["items"][0]["pack_id"] == created["pack_id"]
    replay = client.create_pack(
        input_destination_id=inbox_id,
        drive_file_id=clip_id,
        count=8,
        request_id="mcp-pack-1",
    )
    assert replay["pack_id"] == created["pack_id"]
