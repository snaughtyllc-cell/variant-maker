"""Unit tests for ComfyUI HTTP client."""
from __future__ import annotations

from tests.server.create_fakes import FakeComfyClient
from variant_maker.server.comfy_client import HttpComfyClient


def test_fake_comfy_upload_queue_wait():
    client = FakeComfyClient(images=[b"png-a", b"png-b"])
    name = client.upload_image("face.jpg", b"face")
    assert name == "face.jpg"
    pid = client.queue_prompt({"1": {"class_type": "KSampler"}})
    imgs = client.wait_images(pid)
    assert imgs == [b"png-a", b"png-b"]
    assert client.uploaded == [("face.jpg", b"face")]
    assert client.queued[0]["prompt_id"] == pid


def test_http_comfy_queue_poll_download(monkeypatch):
    posted: dict = {"gets": []}

    class FakeResp:
        def __init__(self, payload=None, content=b"", status=200):
            self._payload = payload
            self.content = content
            self.status_code = status

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"http {self.status_code}")

        def json(self):
            return self._payload

    class FakeHttp:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def post(self, url, json=None, files=None, data=None):
            posted["last_post"] = url
            if url.endswith("/upload/image"):
                return FakeResp({"name": "face.jpg"})
            if url.endswith("/prompt"):
                return FakeResp({"prompt_id": "abc123"})
            raise AssertionError(url)

        def get(self, url, params=None):
            posted["gets"].append((url, params))
            if "/history/" in url:
                if len([g for g in posted["gets"] if "/history/" in g[0]]) == 1:
                    return FakeResp({})  # not ready
                return FakeResp({
                    "abc123": {
                        "outputs": {
                            "9": {
                                "images": [
                                    {"filename": "out_00001_.png", "subfolder": "", "type": "output"},
                                ],
                            },
                        },
                    },
                })
            if url.endswith("/view"):
                return FakeResp(content=b"\x89PNG-real")
            raise AssertionError(url)

    monkeypatch.setattr("variant_maker.server.comfy_client._http", lambda: FakeHttp())
    monkeypatch.setattr("variant_maker.server.comfy_client.time.sleep", lambda *_: None)
    client = HttpComfyClient(base_url="http://127.0.0.1:8188", poll_interval=0)
    assert client.upload_image("face.jpg", b"facebytes") == "face.jpg"
    pid = client.queue_prompt({"3": {"inputs": {}}})
    assert pid == "abc123"
    images = client.wait_images(pid, timeout=5)
    assert images == [b"\x89PNG-real"]
    assert posted["last_post"].endswith("/prompt")


def test_http_comfy_default_url_from_env(monkeypatch):
    monkeypatch.setenv("COMFY_URL", "http://10.0.0.2:8188")
    c = HttpComfyClient.from_env()
    assert c.base_url == "http://10.0.0.2:8188"
