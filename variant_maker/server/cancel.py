"""Per-job cancel: Studio stop + optional RunPod /cancel/{id}.

One token per Studio job so two concurrent packs do not cancel each other.
"""
from __future__ import annotations

import threading


USER_CANCEL_MSG = "Cancelled — New run when you want another pack."


class JobCancelled(Exception):
    """Raised when the user (or RunPod) stops a job mid-flight."""


class CancelToken:
    def __init__(self) -> None:
        self._ev = threading.Event()
        self._lock = threading.Lock()
        self.runpod_job_id: str | None = None
        self._base: str | None = None
        self._headers: dict | None = None

    def is_set(self) -> bool:
        return self._ev.is_set()

    def bind_runpod(self, job_id: str, base_url: str, headers: dict) -> None:
        """Remember the cloud job so cancel() can POST /cancel/{id} from another thread."""
        with self._lock:
            self.runpod_job_id = job_id
            self._base = base_url
            self._headers = dict(headers)
            already = self._ev.is_set()
        if already:
            self._post_cancel()

    def cancel(self) -> None:
        self._ev.set()
        self._post_cancel()

    def _post_cancel(self) -> None:
        with self._lock:
            jid = self.runpod_job_id
            base = self._base
            headers = self._headers
        if not jid or not base:
            return
        try:
            import httpx
            with httpx.Client(timeout=10.0) as http:
                http.post(f"{base}/cancel/{jid}", headers=headers)
        except Exception:
            pass
