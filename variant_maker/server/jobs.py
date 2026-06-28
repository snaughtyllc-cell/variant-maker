"""In-memory job registry + background execution. No DB (Stage 1)."""
from __future__ import annotations

import datetime as _dt
import threading
import uuid
from dataclasses import dataclass, field

from .events import VariantEvent
from .runner import Runner
from .workspace import Workspace


@dataclass
class VariantInfo:
    source_id: str
    index: int
    filename: str
    status: str
    quality: dict


@dataclass
class JobSource:
    source_id: str
    filename: str
    requested: int
    variants: list[VariantInfo] = field(default_factory=list)

    @property
    def delivered(self) -> int:
        return sum(1 for v in self.variants if v.status == "ok")

    @property
    def shortfall(self) -> int:
        return max(0, self.requested - self.delivered)


@dataclass
class Job:
    job_id: str
    count: int
    created_utc: str
    sources: list[JobSource] = field(default_factory=list)
    state: str = "running"
    events: list[VariantEvent] = field(default_factory=list)


def _now() -> str:
    return (_dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)
            .isoformat().replace("+00:00", "Z"))


class JobStore:
    def __init__(self, workspace: Workspace, runner: Runner) -> None:
        self._ws = workspace
        self._runner = runner
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._done: dict[str, threading.Event] = {}

    def create_job(self, uploads: list[tuple[str, bytes]], count: int) -> Job:
        job_id = uuid.uuid4().hex[:12]
        sources = []
        for filename, data in uploads:
            source_id = uuid.uuid4().hex[:12]
            self._ws.save_upload(job_id, source_id, filename, data)
            sources.append(JobSource(source_id=source_id, filename=filename, requested=count))
        job = Job(job_id=job_id, count=count, created_utc=_now(), sources=sources)
        with self._lock:
            self._jobs[job_id] = job
            self._done[job_id] = threading.Event()
        threading.Thread(target=self._run_job, args=(job,), daemon=True).start()
        return job

    def _run_job(self, job: Job) -> None:
        try:
            for source in job.sources:
                in_path = self._ws.source_in_path(job.job_id, source.source_id, source.filename)
                out_dir = self._ws.source_out_dir(job.job_id, source.source_id)

                def on_event(e: VariantEvent) -> None:
                    job.events.append(e)

                result = self._runner.run(
                    in_path, count=job.count, out_dir=out_dir,
                    source_id=source.source_id, on_event=on_event,
                )
                source.variants = [
                    VariantInfo(source_id=source.source_id, index=v.index, filename=v.filename,
                                status=v.status, quality=v.quality)
                    for v in result.variants
                ]
        finally:
            job.state = "done"
            self._done[job.job_id].set()

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        return list(self._jobs.values())

    def wait(self, job_id: str, timeout: float = 30.0) -> bool:
        ev = self._done.get(job_id)
        return ev.wait(timeout) if ev else False

    def gallery(self) -> list[JobSource]:
        with self._lock:
            return [s for job in self._jobs.values() for s in job.sources]

    def diagnostics(self) -> list[VariantInfo]:
        out = []
        with self._lock:
            for job in self._jobs.values():
                for s in job.sources:
                    out.extend(v for v in s.variants if v.status in ("best_effort", "corrupt"))
        return out
