"""varimo-mcp HTTP client: public /api/v1 only, no cookie session, no redirects."""
from __future__ import annotations

import json

import httpx
import pytest

from variant_maker.mcp.client import StudioV1Client, StudioV1Error, validate_base_url


def test_https_required_except_localhost():
    assert validate_base_url("https://studio.example/") == "https://studio.example"
    assert validate_base_url("http://127.0.0.1:8000") == "http://127.0.0.1:8000"
    assert validate_base_url("http://localhost:3000/") == "http://localhost:3000"
    with pytest.raises(ValueError, match="https"):
        validate_base_url("http://studio.example")
    with pytest.raises(ValueError):
        validate_base_url("file:///etc/passwd")


def _client(handler, *, key="vf_test_secret"):
    transport = httpx.MockTransport(handler)
    return StudioV1Client(
        base_url="https://studio.example",
        api_key=key,
        transport=transport,
    )


def test_create_pack_posts_bearer_and_idempotency():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            201,
            json={"pack_id": "p1", "state": "running", "status_url": "/api/v1/packs/p1"},
        )

    out = _client(handler).create_pack(
        input_destination_id="dst_in",
        drive_file_id="file_1",
        count=8,
        request_id="req-pack-1",
    )
    assert out["pack_id"] == "p1"
    req = seen[0]
    assert request_path(req) == "/api/v1/packs"
    assert req.method == "POST"
    assert req.headers["authorization"] == "Bearer vf_test_secret"
    assert req.headers["idempotency-key"] == "req-pack-1"
    assert json.loads(req.content) == {
        "input_destination_id": "dst_in",
        "drive_file_id": "file_1",
        "count": 8,
    }


def request_path(request: httpx.Request) -> str:
    return request.url.path


def test_get_pack_and_gallery_are_gets():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(f"{request.method} {request.url.path}?{request.url.query.decode()}")
        if request.url.path.endswith("/gallery"):
            return httpx.Response(200, json={"items": [], "next_cursor": None})
        return httpx.Response(
            200,
            json={
                "pack_id": "p1",
                "state": "done",
                "requested": 8,
                "ready": 8,
                "shortfall": 0,
                "review_url": "/gallery",
            },
        )

    client = _client(handler)
    pack = client.get_pack("p1")
    gallery = client.list_gallery(pack_id="p1", limit=25)
    assert pack["review_url"] == "/gallery"
    assert gallery["items"] == []
    assert seen[0].startswith("GET /api/v1/packs/p1")
    assert seen[1].startswith("GET /api/v1/gallery")
    assert "pack_id=p1" in seen[1]


def test_send_submit_and_status():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "POST":
            return httpx.Response(
                201,
                json={
                    "export_id": "exp_1",
                    "state": "pending",
                    "status_url": "/api/v1/drive/exports/exp_1",
                    "folder_url": "https://drive.google.com/drive/folders/out",
                },
            )
        return httpx.Response(
            200,
            json={"export_id": "exp_1", "state": "succeeded", "folder_url": "https://drive.google.com/drive/folders/out"},
        )

    client = _client(handler)
    created = client.create_export(
        destination_id="dst_out",
        variants=[{"source_id": "s1", "index": 0}],
        request_id="exp-1",
    )
    status = client.get_export("exp_1")
    assert created["export_id"] == "exp_1"
    assert status["state"] == "succeeded"
    assert seen[0].method == "POST"
    assert request_path(seen[0]) == "/api/v1/drive/exports"
    assert seen[0].headers["idempotency-key"] == "exp-1"
    assert request_path(seen[1]) == "/api/v1/drive/exports/exp_1"


def test_does_not_follow_redirects_or_call_cookie_routes():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/api/jobs"):
            return httpx.Response(200, json={"leaked": True})
        return httpx.Response(302, headers={"location": "https://evil.example/steal"})

    client = _client(handler)
    with pytest.raises(StudioV1Error, match="redirect"):
        client.get_pack("p1")


def test_api_error_does_not_include_token():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "invalid API key"})

    with pytest.raises(StudioV1Error, match="invalid API key") as exc:
        _client(handler, key="vf_super_secret_token").get_pack("p1")
    assert "vf_super_secret_token" not in str(exc.value)


def test_count_must_be_eight_or_twenty():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not call HTTP")

    with pytest.raises(ValueError, match="8 or 20"):
        _client(handler).create_pack(
            input_destination_id="dst_in",
            drive_file_id="file_1",
            count=3,
            request_id="x",
        )
