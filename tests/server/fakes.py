"""A deterministic Runner that needs no ffmpeg — for JobStore / app tests."""
from __future__ import annotations

import os
from typing import Callable

from variant_maker.server.events import VariantEvent
from variant_maker.server.gpu_worker import process_job
from variant_maker.server.runner import SourceResult, VariantResult


class FakeRunner:
    """plan: {variant_index: status}. Emits the full lifecycle and writes placeholder files."""

    def __init__(self, plan: dict[int, str] | None = None) -> None:
        # default (empty plan): every variant is "ok".
        # Pass a {variant_index: status} dict to override specific indices.
        self.plan = plan or {}

    def _status(self, i: int) -> str:
        return self.plan.get(i, "ok")

    def run(self, source_path: str, *, count: int, out_dir: str, source_id: str,
            on_event: Callable[[VariantEvent], None]) -> SourceResult:
        os.makedirs(out_dir, exist_ok=True)
        variants = []
        for i in range(1, count + 1):
            status = self._status(i)
            fname = f"v{i:02d}.mp4"
            on_event(VariantEvent(source_id=source_id, index=i, state="rendering"))
            on_event(VariantEvent(source_id=source_id, index=i, state="checking"))
            on_event(VariantEvent(
                source_id=source_id, index=i, state="done",
                status=status, quality={"vmaf": 95.0 if status == "ok" else 50.0},
                filename=fname,
            ))
            path = os.path.join(out_dir, fname)
            open(path, "w").close()
            variants.append(VariantResult(
                index=i, filename=fname, status=status, quality={"vmaf": 95.0}, path=path,
                uniqueness=0.42 if status == "ok" else None,
                uniqueness_status="ok" if status == "ok" else "unknown",
                uniqueness_metric="phash+hist" if status == "ok" else None,
                uniqueness_target=0.35,
                preset_used="medium", strength_final=1.0, escalated=False,
                platform_result=None,
            ))
        mpath = os.path.join(out_dir, "manifest.json")
        open(mpath, "w").close()
        return SourceResult(variants=variants, manifest_path=mpath)


class FakeRunPodClient:
    """Yields a scripted list of output chunks; ignores the payload. No network."""

    def __init__(self, chunks: list[dict]) -> None:
        self._chunks = chunks

    def stream_run(self, payload: dict):
        yield from self._chunks


class LoopbackRunPodClient:
    """Drives the REAL gpu_worker.process_job against a shared store — no network, no cloud.
    Used to verify the runner<->worker chunk contract end to end."""

    def __init__(self, store, work_dir: str) -> None:
        self._store = store
        self._work_dir = work_dir

    def stream_run(self, payload: dict):
        yield from process_job(payload["input"], self._store, work_dir=self._work_dir)


class FakeObjectStore:
    """In-memory object store for tests — no network, no boto3."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    def put(self, key: str, local_path: str) -> None:
        with open(local_path, "rb") as f:
            self._data[key] = f.read()

    def get(self, key: str, local_path: str) -> None:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(self._data[key])

    def list_prefix(self, prefix: str) -> list[str]:
        return [k for k in self._data if k.startswith(prefix)]
