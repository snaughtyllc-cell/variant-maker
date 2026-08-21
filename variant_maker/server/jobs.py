"""In-memory job registry + background execution. No DB (Stage 1)."""
from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import threading
import uuid
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Literal

from variant_maker.normalize import maybe_normalize_upload

from .cancel import USER_CANCEL_MSG, CancelToken, JobCancelled
from .events import VariantEvent, event_to_dict
from .runner import Runner, normalize_quality_mode
from .workspace import Workspace

PLATFORM_RESULTS = ("passed", "duplicate_reject", "flagged", "unknown")
COPY_FAILED_MSG = (
    "GPU finished, but videos didn't copy back to Studio. "
    "Retry copy, or Regenerate if that still fails."
)


def variant_on_disk(ws: Workspace, job_id: str, source_id: str, filename: str) -> bool:
    if not filename or filename != os.path.basename(filename) or filename in (".", ".."):
        return False
    return os.path.isfile(ws.variant_path(job_id, source_id, filename))


def missing_ok_filenames(source: JobSource, ws: Workspace, job_id: str) -> list[str]:
    missing: list[str] = []
    for v in source.variants:
        if v.status != "ok" or not v.filename:
            continue
        if not variant_on_disk(ws, job_id, source.source_id, v.filename):
            missing.append(v.filename)
    return missing


def source_files_ready(source: JobSource, ws: Workspace, job_id: str) -> int:
    return sum(
        1 for v in source.variants
        if v.status == "ok" and v.filename
        and variant_on_disk(ws, job_id, source.source_id, v.filename)
    )


def source_copy_status(source: JobSource, ws: Workspace, job_id: str,
                       job_state: str | None) -> Literal["ok", "copying", "missing"]:
    """ok = files on disk; copying = job still running; missing = GPU done, files not here."""
    if not missing_ok_filenames(source, ws, job_id):
        return "ok"
    if job_state == "running":
        return "copying"
    return "missing"


@dataclass
class VariantInfo:
    source_id: str
    index: int
    filename: str
    status: str
    quality: dict
    uniqueness: float | None = None
    uniqueness_status: str | None = None
    uniqueness_metric: str | None = None
    uniqueness_target: float | None = None
    preset_used: str | None = None
    strength_final: float | None = None
    escalated: bool = False
    platform_result: str | None = None
    post_url: str | None = None


@dataclass
class JobSource:
    source_id: str
    filename: str
    requested: int
    variants: list[VariantInfo] = field(default_factory=list)
    runpod_job_id: str | None = None

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
    allow_creative_escalate: bool = True
    quality_mode: str = "fast"
    error: str | None = None


def _public_job_error(exc: BaseException) -> str:
    """Short UI string. RunPod FAILED after ~20 min is serial Fast hitting the cap."""
    raw = str(exc)
    if "ended: CANCELLED" in raw:
        return USER_CANCEL_MSG
    if "ended: FAILED" in raw or "TIMED_OUT" in raw.upper():
        return (
            "Job hit the worker time limit before the pack finished. "
            "A 20-pack one-at-a-time often exceeds 20 minutes — New run. "
            "Later Fast packs encode several variants at once. "
            "If this keeps happening, set RunPod execution timeout to 3600s."
        )
    return raw or type(exc).__name__


def _now() -> str:
    return (_dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)
            .isoformat().replace("+00:00", "Z"))


def _variant_to_dict(v: VariantInfo) -> dict:
    return {
        "source_id": v.source_id, "index": v.index, "filename": v.filename,
        "status": v.status, "quality": v.quality, "uniqueness": v.uniqueness,
        "uniqueness_status": v.uniqueness_status, "uniqueness_metric": v.uniqueness_metric,
        "uniqueness_target": v.uniqueness_target, "preset_used": v.preset_used,
        "strength_final": v.strength_final, "escalated": v.escalated,
        "platform_result": v.platform_result, "post_url": v.post_url,
    }


def queue_snapshot(jobs: list[Job]) -> dict:
    """Live generating packs on a shared Studio URL. Filenames only — no video."""
    running = [j for j in jobs if j.state == "running"]
    running.sort(key=lambda j: (j.created_utc or "", j.job_id))
    items = []
    for i, job in enumerate(running, start=1):
        requested = sum(s.requested for s in job.sources)
        if requested <= 0:
            requested = job.count * max(len(job.sources), 1)
        items.append({
            "job_id": job.job_id,
            "quality_mode": job.quality_mode,
            "state": job.state,
            "created_utc": job.created_utc,
            "count": job.count,
            "source_count": len(job.sources),
            "filenames": [s.filename for s in job.sources],
            "delivered": sum(s.delivered for s in job.sources),
            "requested": requested,
            "position": i,
        })
    return {
        "running": len(items),
        "fast": sum(1 for it in items if it["quality_mode"] != "hq"),
        "hq": sum(1 for it in items if it["quality_mode"] == "hq"),
        "jobs": items,
    }


def _variant_from_dict(data: dict, source_id: str) -> VariantInfo:
    quality = data.get("quality") if isinstance(data.get("quality"), dict) else {}
    return VariantInfo(
        source_id=str(data.get("source_id") or source_id),
        index=int(data.get("index") or 0),
        filename=str(data.get("filename") or ""),
        status=str(data.get("status") or "ok"),
        quality=quality,
        uniqueness=data.get("uniqueness"),
        uniqueness_status=data.get("uniqueness_status"),
        uniqueness_metric=data.get("uniqueness_metric"),
        uniqueness_target=data.get("uniqueness_target"),
        preset_used=data.get("preset_used"),
        strength_final=data.get("strength_final"),
        escalated=bool(data.get("escalated") or False),
        platform_result=data.get("platform_result"),
        post_url=data.get("post_url") or None,
    )


def _event_from_dict(data: dict) -> VariantEvent:
    return VariantEvent(
        source_id=str(data.get("source_id") or ""),
        index=int(data.get("index") or 0),
        state=str(data.get("state") or "done"),
        attempt=int(data.get("attempt") or 0),
        max_attempts=int(data.get("max_attempts") or 0),
        status=data.get("status"),
        quality=data.get("quality") if isinstance(data.get("quality"), dict) else None,
        filename=data.get("filename"),
        uniqueness=data.get("uniqueness"),
        uniqueness_status=data.get("uniqueness_status"),
        uniqueness_metric=data.get("uniqueness_metric"),
        uniqueness_target=data.get("uniqueness_target"),
        escalated=bool(data.get("escalated") or False),
        preset_used=data.get("preset_used"),
        strength_final=data.get("strength_final"),
        platform_result=data.get("platform_result"),
    )


def _job_to_dict(job: Job) -> dict:
    return {
        "job_id": job.job_id,
        "count": job.count,
        "created_utc": job.created_utc,
        "state": job.state,
        "quality_mode": job.quality_mode,
        "allow_creative_escalate": job.allow_creative_escalate,
        "error": job.error,
        "sources": [
            {
                "source_id": s.source_id,
                "filename": s.filename,
                "requested": s.requested,
                "runpod_job_id": s.runpod_job_id,
                "variants": [_variant_to_dict(v) for v in s.variants],
            }
            for s in job.sources
        ],
        "events": [event_to_dict(e) for e in job.events],
    }


def _job_from_dict(data: dict) -> Job:
    sources = []
    for raw in data.get("sources") or []:
        if not isinstance(raw, dict):
            continue
        sid = str(raw.get("source_id") or "")
        source = JobSource(
            source_id=sid,
            filename=str(raw.get("filename") or sid),
            requested=int(raw.get("requested") or 0),
            runpod_job_id=raw.get("runpod_job_id"),
        )
        for v in raw.get("variants") or []:
            if isinstance(v, dict):
                source.variants.append(_variant_from_dict(v, sid))
        sources.append(source)
    events = []
    for raw in data.get("events") or []:
        if isinstance(raw, dict):
            events.append(_event_from_dict(raw))
    return Job(
        job_id=str(data.get("job_id") or ""),
        count=int(data.get("count") or max((s.requested for s in sources), default=0)),
        created_utc=str(data.get("created_utc") or _now()),
        sources=sources,
        state=str(data.get("state") or "done"),
        events=events,
        allow_creative_escalate=bool(data.get("allow_creative_escalate", True)),
        quality_mode=normalize_quality_mode(data.get("quality_mode")),
        error=data.get("error"),
    )


def _source_finished(source: JobSource, *, ws: Workspace | None = None,
                     job_id: str | None = None) -> bool:
    """Done only when we have the requested slots AND ok files are on disk.

    Progress events can fill `source.variants` before RunPod copies mp4s back.
    Treating that as finished skipped the copy on Studio restart — Gallery
    showed 5/5 with black thumbs and a 22-byte zip.
    """
    if len(source.variants) < source.requested or source.requested <= 0:
        return False
    if ws is None or not job_id:
        return True
    return not missing_ok_filenames(source, ws, job_id)


class JobStore:
    def __init__(self, workspace: Workspace, runner: Runner, *, workspace_id: str | None = None) -> None:
        self._ws = workspace
        self._runner = runner
        self._workspace_id = workspace_id
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._done: dict[str, threading.Event] = {}
        self._source_index: dict[str, tuple[str, JobSource]] = {}
        self._cancel: dict[str, CancelToken] = {}

    def create_job(self, uploads: list[tuple[str, bytes]], count: int,
                    allow_creative_escalate: bool = True,
                    quality_mode: str = "fast") -> Job:
        job_id = uuid.uuid4().hex[:12]
        sources = []
        for filename, data in uploads:
            source_id = uuid.uuid4().hex[:12]
            self._ws.save_upload(job_id, source_id, filename, data)
            source = JobSource(source_id=source_id, filename=filename, requested=count)
            sources.append(source)
        return self._start_job(job_id, sources, count, allow_creative_escalate, quality_mode)

    def create_job_from_paths(self, paths: list[tuple[str, str]], count: int,
                               allow_creative_escalate: bool = True,
                               quality_mode: str = "fast") -> Job:
        """Create a job from already-staged files: [(filename, abs_path), ...]."""
        job_id = uuid.uuid4().hex[:12]
        sources = []
        for filename, abs_path in paths:
            source_id = uuid.uuid4().hex[:12]
            dest = self._ws.source_in_path(job_id, source_id, filename)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            os.replace(abs_path, dest)
            source = JobSource(source_id=source_id, filename=filename, requested=count)
            sources.append(source)
        return self._start_job(job_id, sources, count, allow_creative_escalate, quality_mode)

    def _start_job(self, job_id: str, sources: list[JobSource], count: int,
                    allow_creative_escalate: bool,                     quality_mode: str = "fast") -> Job:
        job = Job(job_id=job_id, count=count, created_utc=_now(), sources=sources,
                   allow_creative_escalate=allow_creative_escalate,
                   quality_mode=normalize_quality_mode(quality_mode))
        token = CancelToken()
        with self._lock:
            self._jobs[job_id] = job
            self._done[job_id] = threading.Event()
            self._cancel[job_id] = token
            for source in sources:
                self._source_index[source.source_id] = (job_id, source)
        self._persist(job)
        threading.Thread(target=self._run_job, args=(job, token), daemon=True).start()
        return job

    def _workspace_runner_kw(self) -> dict:
        if self._workspace_id and hasattr(self._runner, "acquire_fast"):
            return {"workspace_id": self._workspace_id}
        return {}

    @contextmanager
    def _fast_slot(self, quality_mode: str):
        """Sticky Fast CPU for this workspace. HQ does not take a Fast slot."""
        acquire = getattr(self._runner, "acquire_fast", None)
        leased = False
        if (
            callable(acquire)
            and self._workspace_id
            and normalize_quality_mode(quality_mode) != "hq"
        ):
            acquire(self._workspace_id)
            leased = True
        try:
            yield
        finally:
            if leased:
                release = getattr(self._runner, "release_fast", None)
                if callable(release) and self._workspace_id:
                    release(self._workspace_id)

    def cancel(self, job_id: str) -> Job | None:
        """Stop a running job. Finished jobs are returned unchanged (204-style no-op)."""
        job = self.get(job_id)
        if job is None:
            return None
        token = self._cancel.get(job_id)
        if token is not None:
            token.cancel()
        if job.state == "running":
            job.error = USER_CANCEL_MSG
            self._persist(job)
        return job

    def delete_source(self, source_id: str) -> bool:
        """Remove a pack from Gallery. Cancels a live job first. Deletes Studio files."""
        loc = self._locate(source_id)
        if loc is None:
            return False
        job_id, _source = loc
        job = self._jobs.get(job_id)
        if job is not None and job.state == "running":
            self.cancel(job_id)
        self._ws.remove_source(job_id, source_id)
        with self._lock:
            self._source_index.pop(source_id, None)
            if job is not None:
                job.sources = [s for s in job.sources if s.source_id != source_id]
        if job is None or not job.sources:
            return self.delete_job(job_id)
        self._persist(job)
        return True

    def delete_job(self, job_id: str) -> bool:
        """Drop a job from memory and disk. Cancels if still running."""
        job = self.get(job_id)
        if job is None:
            return False
        if job.state == "running":
            self.cancel(job_id)
        with self._lock:
            self._jobs.pop(job_id, None)
            self._cancel.pop(job_id, None)
            for source in job.sources:
                self._source_index.pop(source.source_id, None)
            ev = self._done.get(job_id)
            if ev is not None:
                ev.set()
            self._ws.remove_job(job_id)
        return True

    def _persist(self, job: Job) -> None:
        """Write job.json so a Studio restart can restore Gallery + resume a live run."""
        path = self._ws.job_meta_path(job.job_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_job_to_dict(job), f)
        with self._lock:
            if job.job_id not in self._jobs:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                return
            os.replace(tmp, path)

    def _run_job(self, job: Job, token: CancelToken, *, skip_finished: bool = False) -> None:
        try:
            with self._fast_slot(job.quality_mode):
                self._render_job_sources(job, token, skip_finished=skip_finished)
        except JobCancelled:
            job.error = USER_CANCEL_MSG
        except Exception as exc:
            # Uncaught pipeline/ffmpeg/RunPod errors previously killed the worker thread
            # while finally still marked the job "done" with 0 variants — UI looked
            # like a silent failure. Log clearly; job still closes in finally.
            if token.is_set():
                job.error = USER_CANCEL_MSG
            else:
                job.error = _public_job_error(exc)
                print(f"job {job.job_id} failed: {type(exc).__name__}: {exc}", flush=True)
        finally:
            if job.job_id not in self._jobs:
                return
            job.state = "cancelled" if token.is_set() else "done"
            if job.state == "done":
                for source in job.sources:
                    self._pull_missing_outputs(source.source_id)
                self._refresh_copy_error(job)
            self._persist(job)
            self._done[job.job_id].set()

    def _render_job_sources(self, job: Job, token: CancelToken, *, skip_finished: bool) -> None:
        def on_event(e: VariantEvent) -> None:
            job.events.append(e)
            if token.runpod_job_id:
                for source in job.sources:
                    if source.source_id == e.source_id:
                        source.runpod_job_id = token.runpod_job_id
                        break
            # Record finished variants immediately so polling clients (and
            # proxies that buffer SSE) can see progress before the source ends.
            if e.state == "done" and e.filename and e.status and e.quality is not None:
                for source in job.sources:
                    if source.source_id != e.source_id:
                        continue
                    if any(v.index == e.index for v in source.variants):
                        break
                    source.variants.append(VariantInfo(
                        source_id=e.source_id, index=e.index, filename=e.filename,
                        status=e.status, quality=e.quality,
                        uniqueness=e.uniqueness, uniqueness_status=e.uniqueness_status,
                        uniqueness_metric=e.uniqueness_metric,
                        uniqueness_target=e.uniqueness_target,
                        preset_used=e.preset_used, strength_final=e.strength_final,
                        escalated=e.escalated, platform_result=e.platform_result,
                    ))
                    break
            if e.state == "done" or token.runpod_job_id:
                self._persist(job)

        for source in job.sources:
            if token.is_set():
                raise JobCancelled()
            if skip_finished:
                self._pull_missing_outputs(source.source_id)
            if skip_finished and _source_finished(
                source, ws=self._ws, job_id=job.job_id,
            ):
                continue
            in_path = self._ws.source_in_path(job.job_id, source.source_id, source.filename)
            proxied = maybe_normalize_upload(in_path)
            new_name = os.path.basename(proxied)
            if new_name != source.filename:
                source.filename = new_name
                self._persist(job)
            in_path = proxied
            out_dir = self._ws.source_out_dir(job.job_id, source.source_id)
            resume = getattr(self._runner, "resume_run", None)
            if skip_finished and callable(resume) and source.runpod_job_id:
                try:
                    result = resume(
                        in_path, count=job.count, out_dir=out_dir,
                        source_id=source.source_id, on_event=on_event,
                        allow_creative_escalate=job.allow_creative_escalate,
                        quality_mode=job.quality_mode,
                        cancel_token=token,
                        runpod_job_id=source.runpod_job_id,
                        **self._workspace_runner_kw(),
                    )
                except Exception as exc:
                    print(
                        f"job {job.job_id} resume {source.runpod_job_id} failed "
                        f"({type(exc).__name__}: {exc}); re-running source",
                        flush=True,
                    )
                    result = self._runner.run(
                        in_path, count=job.count, out_dir=out_dir,
                        source_id=source.source_id, on_event=on_event,
                        allow_creative_escalate=job.allow_creative_escalate,
                        quality_mode=job.quality_mode,
                        cancel_token=token,
                        **self._workspace_runner_kw(),
                    )
            else:
                result = self._runner.run(
                    in_path, count=job.count, out_dir=out_dir,
                    source_id=source.source_id, on_event=on_event,
                    allow_creative_escalate=job.allow_creative_escalate,
                    quality_mode=job.quality_mode,
                    cancel_token=token,
                    **self._workspace_runner_kw(),
                )
            source.variants = [
                VariantInfo(
                    source_id=source.source_id, index=v.index, filename=v.filename,
                    status=v.status, quality=v.quality,
                    uniqueness=v.uniqueness, uniqueness_status=v.uniqueness_status,
                    uniqueness_metric=v.uniqueness_metric, uniqueness_target=v.uniqueness_target,
                    preset_used=v.preset_used, strength_final=v.strength_final,
                    escalated=v.escalated, platform_result=v.platform_result,
                )
                for v in result.variants
            ]
            source.runpod_job_id = None
            self._persist(job)

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        return list(self._jobs.values())

    def queue(self) -> dict:
        with self._lock:
            jobs = list(self._jobs.values())
        return queue_snapshot(jobs)

    def _install_hydrated_job(self, job: Job) -> None:
        token = CancelToken()
        resume = job.state == "running"
        if resume:
            job.state = "running"
        with self._lock:
            self._jobs[job.job_id] = job
            self._done[job.job_id] = threading.Event()
            for source in job.sources:
                self._source_index[source.source_id] = (job.job_id, source)
            if resume:
                self._cancel[job.job_id] = token
            else:
                self._done[job.job_id].set()
        for source in job.sources:
            self._pull_missing_outputs(source.source_id)
        if not resume:
            self._refresh_copy_error(job)
            self._persist(job)
        if resume:
            threading.Thread(
                target=self._run_job, args=(job, token),
                kwargs={"skip_finished": True}, daemon=True,
            ).start()

    def hydrate_from_disk(self) -> int:
        """Rebuild in-memory jobs from job.json (preferred) or manifests after restart.

        Running snapshots are resumed (skip sources that already finished). Returns how
        many jobs were loaded (skips ids already present).
        """
        jobs_root = os.path.join(self._ws.root, "jobs")
        if not os.path.isdir(jobs_root):
            return 0
        loaded = 0
        for job_id in sorted(os.listdir(jobs_root)):
            job_dir = os.path.join(jobs_root, job_id)
            if not os.path.isdir(job_dir) or job_id in self._jobs:
                continue
            meta_path = self._ws.job_meta_path(job_id)
            if os.path.isfile(meta_path):
                try:
                    with open(meta_path, encoding="utf-8") as f:
                        data = json.load(f)
                except (OSError, json.JSONDecodeError):
                    data = None
                if isinstance(data, dict) and data.get("job_id"):
                    job = _job_from_dict(data)
                    self._install_hydrated_job(job)
                    loaded += 1
                    continue
            sources: list[JobSource] = []
            created_utc = None
            count = 0
            quality_mode = "fast"
            for source_id in sorted(os.listdir(job_dir)):
                source_dir = os.path.join(job_dir, source_id)
                if not os.path.isdir(source_dir):
                    continue
                manifest_path = os.path.join(source_dir, "out", "manifest.json")
                if not os.path.isfile(manifest_path):
                    continue
                try:
                    with open(manifest_path, encoding="utf-8") as f:
                        data = json.load(f)
                except (OSError, json.JSONDecodeError):
                    continue
                if not isinstance(data, dict):
                    continue
                if created_utc is None:
                    created_utc = data.get("created_utc") or _now()
                run = data.get("run") if isinstance(data.get("run"), dict) else {}
                requested = int(run.get("count") or len(data.get("variants") or []) or 0)
                count = max(count, requested)
                quality_mode = normalize_quality_mode(run.get("quality_mode"), default=quality_mode)
                filename = source_id
                in_dir = os.path.join(source_dir, "in")
                if os.path.isdir(in_dir):
                    names = sorted(n for n in os.listdir(in_dir) if not n.startswith("."))
                    if names:
                        filename = names[0]
                source = JobSource(source_id=source_id, filename=filename, requested=requested)
                for v in data.get("variants") or []:
                    if not isinstance(v, dict):
                        continue
                    quality = v.get("quality") if isinstance(v.get("quality"), dict) else {}
                    source.variants.append(VariantInfo(
                        source_id=source_id,
                        index=int(v.get("index") or 0),
                        filename=str(v.get("filename") or ""),
                        status=str(v.get("status") or "ok"),
                        quality=quality,
                        uniqueness=v.get("uniqueness"),
                        uniqueness_status=v.get("uniqueness_status"),
                        uniqueness_metric=v.get("uniqueness_metric"),
                        uniqueness_target=v.get("uniqueness_target"),
                        preset_used=v.get("preset_used"),
                        strength_final=v.get("strength_final"),
                        escalated=bool(v.get("escalated") or False),
                        platform_result=v.get("platform_result"),
                        post_url=v.get("post_url") or None,
                    ))
                sources.append(source)
            if not sources:
                continue
            job = Job(
                job_id=job_id,
                count=count or max((s.requested for s in sources), default=0),
                created_utc=str(created_utc or _now()),
                sources=sources,
                state="done",
                quality_mode=quality_mode,
            )
            self._install_hydrated_job(job)
            loaded += 1
        return loaded

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

    def _locate(self, source_id: str) -> tuple[str, JobSource] | None:
        return self._source_index.get(source_id)

    def get_variant(self, source_id: str, index: int) -> VariantInfo | None:
        loc = self._locate(source_id)
        if loc is None:
            return None
        _, source = loc
        return next((v for v in source.variants if v.index == index), None)

    def find_variant(self, source_id: str, filename: str) -> str | None:
        loc = self._locate(source_id)
        if loc is None:
            return None
        # filename is user-controlled (URL path segment); reject anything that is
        # not a bare basename to prevent path traversal outside the workspace.
        if filename != os.path.basename(filename) or filename in ("", ".", ".."):
            return None
        job_id, _ = loc
        path = self._ws.variant_path(job_id, source_id, filename)
        if os.path.isfile(path):
            return path
        self._pull_missing_outputs(source_id)
        return path if os.path.isfile(path) else None

    def _pull_missing_outputs(self, source_id: str) -> None:
        """Copy variant mp4s from object storage when job.json has them but disk doesn't."""
        fetch = getattr(self._runner, "fetch_outputs", None)
        if not callable(fetch):
            return
        loc = self._locate(source_id)
        if loc is None:
            return
        job_id, source = loc
        names = [v.filename for v in source.variants if v.status == "ok" and v.filename]
        if not names:
            return
        fetch(source_id, self._ws.source_out_dir(job_id, source_id), names)

    def _refresh_copy_error(self, job: Job) -> None:
        """Surface a VA-facing error when GPU metadata is ok but mp4s never landed."""
        if job.state != "done":
            return
        if job.error and job.error != COPY_FAILED_MSG:
            return
        missing = any(
            missing_ok_filenames(source, self._ws, job.job_id) for source in job.sources
        )
        job.error = COPY_FAILED_MSG if missing else None

    def retry_copy(self, source_id: str) -> JobSource | None:
        """Re-pull missing ok variants from object storage. Does not re-run the GPU."""
        loc = self._locate(source_id)
        if loc is None:
            return None
        job_id, source = loc
        self._pull_missing_outputs(source_id)
        job = self._jobs.get(job_id)
        if job is not None:
            self._refresh_copy_error(job)
            self._persist(job)
        return source

    def source_file(self, source_id: str) -> str | None:
        loc = self._locate(source_id)
        if loc is None:
            return None
        # Uses the stored source.filename (not user input) -> no traversal risk.
        job_id, source = loc
        path = self._ws.source_in_path(job_id, source_id, source.filename)
        return path if os.path.exists(path) else None

    def regenerate(self, source_id: str, n: int) -> JobSource | None:
        loc = self._locate(source_id)
        if loc is None:
            return None
        job_id, source = loc
        out_dir = self._ws.source_out_dir(job_id, source_id)
        # NOTE — manifest gap (latent, no fix needed yet):
        # runner.run writes a new manifest.json into out_dir containing ONLY the newly-rendered
        # batch, clobbering the original source manifest. source.variants (in-memory) is the
        # authoritative variant record for the API and is unaffected. Any future route that
        # serves manifest.json from disk must merge/preserve the original manifest first.
        start = max((v.index for v in source.variants), default=0)
        job = self._jobs.get(job_id)
        allow_creative_escalate = job.allow_creative_escalate if job else True
        quality_mode = job.quality_mode if job else "fast"
        with self._fast_slot(quality_mode):
            result = self._runner.run(
                self._ws.source_in_path(job_id, source_id, source.filename),
                count=n, out_dir=out_dir, source_id=source_id, on_event=lambda e: None,
                allow_creative_escalate=allow_creative_escalate,
                quality_mode=quality_mode,
                **self._workspace_runner_kw(),
            )
        for v in result.variants:
            source.variants.append(VariantInfo(
                source_id=source_id, index=start + v.index, filename=v.filename,
                status=v.status, quality=v.quality,
                uniqueness=v.uniqueness, uniqueness_status=v.uniqueness_status,
                uniqueness_metric=v.uniqueness_metric, uniqueness_target=v.uniqueness_target,
                preset_used=v.preset_used, strength_final=v.strength_final,
                escalated=v.escalated, platform_result=v.platform_result,
            ))
        return source

    def set_platform_result(self, source_id: str, index: int, result: str) -> VariantInfo | None:
        if result not in PLATFORM_RESULTS:
            raise ValueError(f"invalid platform_result: {result!r}")
        loc = self._locate(source_id)
        if loc is None:
            return None
        job_id, source = loc
        variant = next((v for v in source.variants if v.index == index), None)
        if variant is None:
            return None
        variant.platform_result = result
        self._rewrite_manifest_fields(job_id, source_id, index, platform_result=result)
        job = self._jobs.get(job_id)
        if job is not None:
            self._persist(job)
        return variant

    def set_post_url(self, source_id: str, index: int, url: str | None) -> VariantInfo | None:
        loc = self._locate(source_id)
        if loc is None:
            return None
        job_id, source = loc
        variant = next((v for v in source.variants if v.index == index), None)
        if variant is None:
            return None
        variant.post_url = url
        self._rewrite_manifest_fields(job_id, source_id, index, post_url=url)
        job = self._jobs.get(job_id)
        if job is not None:
            self._persist(job)
        return variant

    def _rewrite_manifest_fields(self, job_id: str, source_id: str, index: int,
                                 **fields: object) -> None:
        out_dir = self._ws.source_out_dir(job_id, source_id)
        path = os.path.join(out_dir, "manifest.json")
        try:
            with open(path) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return
        changed = False
        for v in data.get("variants", []):
            if v.get("index") == index:
                v.update(fields)
                changed = True
        if changed:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)

    def zip_ok_variants(self, source_id: str) -> str | None:
        loc = self._locate(source_id)
        if loc is None:
            return None
        job_id, source = loc
        self._pull_missing_outputs(source_id)
        members: list[tuple[str, str]] = []
        for v in source.variants:
            if v.status != "ok" or not v.filename:
                continue
            fpath = self.find_variant(source_id, v.filename)
            if fpath:
                members.append((fpath, os.path.basename(v.filename)))
        if not members:
            return None
        out_dir = self._ws.source_out_dir(job_id, source_id)
        os.makedirs(out_dir, exist_ok=True)
        zip_path = os.path.join(out_dir, f"{source_id}_variants.zip")
        tmp_path = zip_path + ".tmp"
        # STORED: mp4s are already compressed; iOS Files is picky about deflate-empty archives.
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_STORED) as zf:
            for fpath, name in members:
                zf.write(fpath, arcname=name)
        os.replace(tmp_path, zip_path)
        return zip_path
