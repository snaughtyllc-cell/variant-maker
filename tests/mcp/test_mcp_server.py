"""varimo-mcp stdio tools wrap /api/v1. No base URL or token arguments."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from variant_maker.mcp.client import StudioV1Client
from variant_maker.mcp.server import TOOL_NAMES, build_server, send_to_drive_args


def _server(handler):
    client = StudioV1Client(
        base_url="https://studio.example",
        api_key="vf_test_secret",
        transport=httpx.MockTransport(handler),
    )
    return build_server(client=client)


def test_lists_the_four_loop_tools():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("list_tools is local")

    server = _server(handler)
    tools = asyncio.run(server.list_tools())
    names = sorted(t.name for t in tools)
    assert names == sorted(TOOL_NAMES)
    blob = json.dumps([t.model_dump() if hasattr(t, "model_dump") else t.dict() for t in tools])
    assert "VARIMO_API_KEY" not in blob
    assert "base_url" not in blob
    assert "api_key" not in blob


def test_create_pack_tool_does_not_wait_for_ready():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201,
            json={"pack_id": "p1", "state": "running", "status_url": "/api/v1/packs/p1"},
        )

    server = _server(handler)
    result = asyncio.run(server.call_tool(
        "create_pack",
        {
            "input_destination_id": "dst_in",
            "drive_file_id": "file_1",
            "count": 8,
            "request_id": "req-1",
        },
    ))
    text = _tool_text(result)
    body = json.loads(text)
    assert body["pack_id"] == "p1"
    assert body["state"] == "running"


def test_send_to_drive_schemas_are_exclusive():
    with pytest.raises(ValueError, match="export_id"):
        send_to_drive_args(
            export_id="exp_1",
            destination_id="dst",
            variants=[{"source_id": "s", "index": 0}],
            request_id="r",
        )
    kind, payload = send_to_drive_args(export_id="exp_1")
    assert kind == "status" and payload == "exp_1"
    kind, payload = send_to_drive_args(
        destination_id="dst_out",
        variants=[{"source_id": "s1", "index": 0}],
        request_id="exp-1",
    )
    assert kind == "submit"


def _tool_text(result) -> str:
    if isinstance(result, tuple):
        result = result[0]
    if isinstance(result, dict):
        return json.dumps(result)
    texts = []
    for block in result:
        text = getattr(block, "text", None)
        if text:
            texts.append(text)
        elif isinstance(block, dict) and block.get("text"):
            texts.append(block["text"])
    return "\n".join(texts)
