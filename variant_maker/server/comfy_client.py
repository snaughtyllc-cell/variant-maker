"""ComfyUI HTTP client: upload images, queue prompts, poll history, download outputs."""
from __future__ import annotations

import os
import time
from typing import Protocol


DEFAULT_COMFY_URL = "http://127.0.0.1:8188"


class ComfyClient(Protocol):
    def upload_image(self, filename: str, data: bytes) -> str: ...
    def queue_prompt(self, workflow: dict) -> str: ...
    def wait_images(self, prompt_id: str, *, timeout: float = 300.0) -> list[bytes]: ...


def _http():
    import httpx  # lazy: only the real client needs it
    return httpx.Client(timeout=120.0)


class HttpComfyClient:
    def __init__(self, *, base_url: str = DEFAULT_COMFY_URL, poll_interval: float = 1.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.poll_interval = poll_interval

    @classmethod
    def from_env(cls) -> HttpComfyClient:
        return cls(base_url=os.environ.get("COMFY_URL", DEFAULT_COMFY_URL))

    def upload_image(self, filename: str, data: bytes) -> str:
        with _http() as http:
            resp = http.post(
                f"{self.base_url}/upload/image",
                files={"image": (filename, data, "application/octet-stream")},
                data={"overwrite": "true"},
            )
            resp.raise_for_status()
            body = resp.json()
            return body.get("name") or filename

    def queue_prompt(self, workflow: dict) -> str:
        with _http() as http:
            resp = http.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow},
            )
            resp.raise_for_status()
            return resp.json()["prompt_id"]

    def wait_images(self, prompt_id: str, *, timeout: float = 300.0) -> list[bytes]:
        deadline = time.monotonic() + timeout
        with _http() as http:
            while True:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"Comfy prompt {prompt_id} timed out after {timeout}s")
                hist = http.get(f"{self.base_url}/history/{prompt_id}")
                hist.raise_for_status()
                body = hist.json()
                entry = body.get(prompt_id)
                if entry:
                    refs = _image_refs(entry)
                    if refs:
                        return [self._download(http, ref) for ref in refs]
                if self.poll_interval:
                    time.sleep(self.poll_interval)

    def _download(self, http, ref: dict) -> bytes:
        resp = http.get(
            f"{self.base_url}/view",
            params={
                "filename": ref["filename"],
                "subfolder": ref.get("subfolder", ""),
                "type": ref.get("type", "output"),
            },
        )
        resp.raise_for_status()
        return resp.content


def _image_refs(history_entry: dict) -> list[dict]:
    refs: list[dict] = []
    for _node_id, output in (history_entry.get("outputs") or {}).items():
        for img in output.get("images") or []:
            refs.append({
                "filename": img["filename"],
                "subfolder": img.get("subfolder", ""),
                "type": img.get("type", "output"),
            })
    return refs
