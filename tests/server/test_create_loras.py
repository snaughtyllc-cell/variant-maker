"""LoRA library + identity-mode Create API tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from tests.server.create_fakes import FakeCreateRunner
from variant_maker.server.app import create_app
from variant_maker.server.create_api import CreateJobStore
from variant_maker.server.create_loras import LoraLibrary
from variant_maker.server.workspace import Workspace


def _client(tmp_path, runner=None):
    ws = Workspace(str(tmp_path / "create"))
    lib = LoraLibrary(
        str(tmp_path / "create_loras"),
        comfy_loras_dir=str(tmp_path / "comfy_loras"),
    )
    store = CreateJobStore(ws, runner or FakeCreateRunner(), lora_library=lib)
    return TestClient(create_app(create_store=store)), store


def _upload_lora(client, *, name="Creator A", trigger="ohwx", strength="0.75"):
    return client.post(
        "/api/create/loras",
        data={
            "name": name,
            "trigger_word": trigger,
            "default_strength": strength,
        },
        files=[("file", ("creator.safetensors", b"lora-weights", "application/octet-stream"))],
    )


def test_lora_upload_list_get_delete(tmp_path):
    client, store = _client(tmp_path)
    resp = _upload_lora(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"]
    assert body["name"] == "Creator A"
    assert body["trigger_word"] == "ohwx"
    assert body["default_strength"] == 0.75
    assert body["comfy_name"].endswith(".safetensors")
    assert body["comfy_name"].startswith("create_")

    listed = client.get("/api/create/loras").json()
    assert len(listed) == 1
    assert listed[0]["id"] == body["id"]

    got = client.get(f"/api/create/loras/{body['id']}").json()
    assert got["name"] == "Creator A"

    # Weight copied into Comfy loras dir
    weight = store.loras.weight_path(body["id"])
    assert weight and open(weight, "rb").read() == b"lora-weights"
    comfy_path = tmp_path / "comfy_loras" / body["comfy_name"]
    assert comfy_path.is_file()

    del_resp = client.delete(f"/api/create/loras/{body['id']}")
    assert del_resp.status_code == 204
    assert client.get("/api/create/loras").json() == []
    assert client.get(f"/api/create/loras/{body['id']}").status_code == 404


def test_lora_upload_rejects_non_safetensors(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.post(
        "/api/create/loras",
        data={"name": "bad"},
        files=[("file", ("x.ckpt", b"nope", "application/octet-stream"))],
    )
    assert resp.status_code == 422


def test_create_job_lora_only(tmp_path):
    client, store = _client(tmp_path)
    lora_id = _upload_lora(client).json()["id"]
    resp = client.post(
        "/api/create/jobs",
        data={
            "brief": "hotel mirror selfie",
            "aspect": "9:16",
            "count": "1",
            "lora_id": lora_id,
            "lora_strength": "0.9",
        },
    )
    assert resp.status_code == 201
    job_id = resp.json()["job_id"]
    assert store.wait(job_id, timeout=5)
    detail = client.get(f"/api/create/jobs/{job_id}").json()
    assert detail["state"] == "done"
    assert detail["identity_mode"] == "lora"
    assert detail["lora_id"] == lora_id
    assert detail["lora_strength"] == 0.9
    assert len(detail["stills"]) == 1


def test_create_job_both_face_and_lora(tmp_path):
    client, store = _client(tmp_path)
    lora_id = _upload_lora(client).json()["id"]
    resp = client.post(
        "/api/create/jobs",
        data={
            "brief": "bathroom soft flash",
            "aspect": "9:16",
            "count": "1",
            "lora_id": lora_id,
        },
        files=[("face_refs", ("face.jpg", b"facebytes", "image/jpeg"))],
    )
    assert resp.status_code == 201
    job_id = resp.json()["job_id"]
    assert store.wait(job_id, timeout=5)
    detail = client.get(f"/api/create/jobs/{job_id}").json()
    assert detail["identity_mode"] == "both"
    assert detail["lora_id"] == lora_id


def test_create_job_requires_face_or_lora(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.post(
        "/api/create/jobs",
        data={"brief": "no identity", "aspect": "9:16", "count": "1"},
    )
    assert resp.status_code == 422
    assert "face_ref" in resp.json()["detail"] or "lora" in resp.json()["detail"]


def test_create_job_unknown_lora_id(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.post(
        "/api/create/jobs",
        data={
            "brief": "x",
            "aspect": "9:16",
            "count": "1",
            "lora_id": "doesnotexist",
        },
    )
    assert resp.status_code == 422


def test_train_lora_stub_explains_upload(tmp_path):
    client, _ = _client(tmp_path)
    resp = client.post(
        "/api/create/loras/train",
        data={"name": "Creator"},
        files=[("photos", ("a.jpg", b"img", "image/jpeg"))],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "unavailable"
    assert "upload" in body["message"].lower()
    assert "train_lora.md" in body["docs"]
