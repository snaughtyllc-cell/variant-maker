"""RunPod serverless client seam: submit a job and stream its output chunks."""
from __future__ import annotations

import os
import time
from typing import Iterator, Protocol


class RunPodClient(Protocol):
    def stream_run(self, payload: dict, cancel_token=None) -> Iterator[dict]: ...


def _http():
    import httpx  # lazy: only the real client needs it
    # Generate jobs can sit in queue for minutes; each poll should still return quickly,
    # but a 60s global timeout is too tight around GPU cold start.
    return httpx.Client(timeout=httpx.Timeout(10.0, read=300.0))


class HttpRunPodClient:
    def __init__(self, *, endpoint_id: str, api_key: str,
                 base_url: str = "https://api.runpod.ai/v2", poll_interval: float = 1.0,
                 max_seconds: float | None = None) -> None:
        self.endpoint_id = endpoint_id
        self._base = f"{base_url}/{endpoint_id}"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._poll = poll_interval
        raw = os.environ.get("VARIANT_RUNPOD_MAX_SECONDS", "") if max_seconds is None else max_seconds
        try:
            self._max_seconds = float(raw) if raw not in (None, "") else 3600.0
        except (TypeError, ValueError):
            self._max_seconds = 3600.0

    def stream_run(self, payload: dict, cancel_token=None) -> Iterator[dict]:
        from .cancel import JobCancelled

        with _http() as http:
            if cancel_token is not None and cancel_token.is_set():
                raise JobCancelled()
            resp = http.post(f"{self._base}/run", json=payload, headers=self._headers)
            resp.raise_for_status()
            job_id = resp.json()["id"]
            yield {
                "type": "submitted",
                "runpod_job_id": job_id,
                "endpoint_id": self.endpoint_id,
            }
            yield from self._poll_stream(http, job_id, cancel_token)

    def status(self, job_id: str) -> str | None:
        with _http() as http:
            r = http.get(f"{self._base}/status/{job_id}", headers=self._headers)
            r.raise_for_status()
            return r.json().get("status")

    def stream_resume(self, job_id: str, cancel_token=None) -> Iterator[dict]:
        from .cancel import JobCancelled

        with _http() as http:
            if cancel_token is not None and cancel_token.is_set():
                raise JobCancelled()
            yield from self._poll_stream(http, job_id, cancel_token)

    def _poll_stream(self, http, job_id: str, cancel_token=None) -> Iterator[dict]:
        from .cancel import JobCancelled

        started = time.monotonic()
        if cancel_token is not None:
            cancel_token.bind_runpod(job_id, self._base, self._headers)
            if cancel_token.is_set():
                raise JobCancelled()
        while True:
            if cancel_token is not None and cancel_token.is_set():
                cancel_token.cancel()
                raise JobCancelled()
            if self._max_seconds and (time.monotonic() - started) > self._max_seconds:
                if cancel_token is not None:
                    cancel_token.cancel()
                raise RuntimeError(
                    f"RunPod job {job_id} exceeded max execution "
                    f"({int(self._max_seconds)}s)"
                )
            r = http.get(f"{self._base}/stream/{job_id}", headers=self._headers)
            r.raise_for_status()
            body = r.json()
            for item in body.get("stream", []):
                yield item["output"]
            status = body.get("status")
            if status in ("COMPLETED", "FAILED", "CANCELLED"):
                if status == "CANCELLED":
                    raise JobCancelled()
                if status != "COMPLETED":
                    raise RuntimeError(f"RunPod job {job_id} ended: {status}")
                return
            if self._poll:
                time.sleep(self._poll)
