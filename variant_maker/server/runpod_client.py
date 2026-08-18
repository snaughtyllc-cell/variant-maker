"""RunPod serverless client seam: submit a job and stream its output chunks."""
from __future__ import annotations

import time
from typing import Iterator, Protocol


class RunPodClient(Protocol):
    def stream_run(self, payload: dict) -> Iterator[dict]: ...


def _http():
    import httpx  # lazy: only the real client needs it
    # Generate jobs can sit in queue for minutes; each poll should still return quickly,
    # but a 60s global timeout is too tight around GPU cold start.
    return httpx.Client(timeout=httpx.Timeout(10.0, read=300.0))


class HttpRunPodClient:
    def __init__(self, *, endpoint_id: str, api_key: str,
                 base_url: str = "https://api.runpod.ai/v2", poll_interval: float = 1.0) -> None:
        self._base = f"{base_url}/{endpoint_id}"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._poll = poll_interval

    def stream_run(self, payload: dict) -> Iterator[dict]:
        with _http() as http:
            resp = http.post(f"{self._base}/run", json=payload, headers=self._headers)
            resp.raise_for_status()
            job_id = resp.json()["id"]
            while True:
                r = http.get(f"{self._base}/stream/{job_id}", headers=self._headers)
                r.raise_for_status()
                body = r.json()
                for item in body.get("stream", []):
                    yield item["output"]
                status = body.get("status")
                if status in ("COMPLETED", "FAILED", "CANCELLED"):
                    if status != "COMPLETED":
                        raise RuntimeError(f"RunPod job {job_id} ended: {status}")
                    return
                if self._poll:
                    time.sleep(self._poll)
