"""In-memory job registry + background execution. No DB (Stage 1)."""
from __future__ import annotations

import datetime as _dt
import json
import os
import threading
import uuid
import zipfile
from dataclasses import dataclass, field

from .events import VariantEvent
from .runner import Runner
from .workspace import Workspace
from variant_maker.normalize import maybe_normalize_upload

PLATFORM_RESULTS = ("passed", "duplicate_reject", "flagged", "unknown")


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
    allow_creative_escalate: bool = True


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
        self._source_index: dict[str, tuple[str, JobSource]] = {}

    def create_job(self, uploads: list[tuple[str, bytes]], count: int,
                    allow_creative_escalate: bool = True) -> Job:
        job_id = uuid.uuid4().hex[:12]
        sources = []
        for filename, data in uploads:
            source_id = uuid.uuid4().hex[:12]
            self._ws.save_upload(job_id, source_id, filename, data)
            source = JobSource(source_id=source_id, filename=filename, requested=count)
            sources.append(source)
        return self._start_job(job_id, sources, count, allow_creative_escalate)

    def create_job_from_paths(self, paths: list[tuple[str, str]], count: int,
                               allow_creative_escalate: bool = True) -> Job:
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
        return self._start_job(job_id, sources, count, allow_creative_escalate)

    def _start_job(self, job_id: str, sources: list[JobSource], count: int,
                    allow_creative_escalate: bool) -> Job:
        job = Job(job_id=job_id, count=count, created_utc=_now(), sources=sources,
                   allow_creative_escalate=allow_creative_escalate)
        with self._lock:
            self._jobs[job_id] = job
            self._done[job_id] = threading.Event()
            for source in sources:
                self._source_index[source.source_id] = (job_id, source)
        threading.Thread(target=self._run_job, args=(job,), daemon=True).start()
        return job

    def _run_job(self, job: Job) -> None:
        try:
            def on_event(e: VariantEvent) -> None:
                job.events.append(e)
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

            for source in job.sources:
                in_path = self._ws.source_in_path(job.job_id, source.source_id, source.filename)
                in_path = maybe_normalize_upload(in_path)
                source.filename = os.path.basename(in_path)
                out_dir = self._ws.source_out_dir(job.job_id, source.source_id)
                result = self._runner.run(
                    in_path, count=job.count, out_dir=out_dir,
                    source_id=source.source_id, on_event=on_event,
                    allow_creative_escalate=job.allow_creative_escalate,
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
        except Exception as exc:
            # Uncaught pipeline/ffmpeg errors previously killed the worker thread
            # while finally still marked the job "done" with 0 variants — UI looked
            # like a silent failure. Log clearly; job still closes in finally.
            print(f"job {job.job_id} failed: {type(exc).__name__}: {exc}", flush=True)
        finally:
            job.state = "done"
            self._done[job.job_id].set()

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        return list(self._jobs.values())

    def hydrate_from_disk(self) -> int:
        """Rebuild in-memory jobs from ``jobs/*/…/out/manifest.json`` after restart.

        Does not re-run pipelines. Returns how many jobs were loaded (skips ids
        already present). Enables Gallery + platform_result after server restart.
        """
        jobs_root = os.path.join(self._ws.root, "jobs")
        if not os.path.isdir(jobs_root):
            return 0
        loaded = 0
        for job_id in sorted(os.listdir(jobs_root)):
            job_dir = os.path.join(jobs_root, job_id)
            if not os.path.isdir(job_dir) or job_id in self._jobs:
                continue
            sources: list[JobSource] = []
            created_utc = None
            count = 0
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
            )
            with self._lock:
                self._jobs[job_id] = job
                self._done[job_id] = threading.Event()
                self._done[job_id].set()
                for source in sources:
                    self._source_index[source.source_id] = (job_id, source)
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
        return path if os.path.exists(path) else None

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
        result = self._runner.run(
            self._ws.source_in_path(job_id, source_id, source.filename),
            count=n, out_dir=out_dir, source_id=source_id, on_event=lambda e: None,
            allow_creative_escalate=allow_creative_escalate,
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
        self._rewrite_manifest_platform_result(job_id, source_id, index, result)
        return variant

    def _rewrite_manifest_platform_result(self, job_id: str, source_id: str,
                                          index: int, result: str) -> None:
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
                v["platform_result"] = result
                changed = True
        if changed:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)

    def zip_ok_variants(self, source_id: str) -> str | None:
        loc = self._locate(source_id)
        if loc is None:
            return None
        job_id, source = loc
        ok_variants = [v for v in source.variants if v.status == "ok"]
        if not ok_variants:
            return None
        out_dir = self._ws.source_out_dir(job_id, source_id)
        zip_path = os.path.join(out_dir, f"{source_id}_variants.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for v in ok_variants:
                fpath = os.path.join(out_dir, v.filename)
                if os.path.exists(fpath):
                    zf.write(fpath, arcname=v.filename)
        return zip_path
