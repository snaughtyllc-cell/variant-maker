"""In-memory job registry + background execution. No DB (Stage 1)."""
from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import threading
import uuid
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from variant_maker.normalize import maybe_normalize_upload

from .cancel import USER_CANCEL_MSG, CancelToken, JobCancelled
from .caption_ai import brief_from_filename, briefs_for_sources, captions_for_source
from .captions import strip_internal_index_lines
from .events import VariantEvent, event_to_dict
from .job_metrics import (
    finalize_telemetry,
    merge_telemetry,
    processing_charge_label,
    source_snapshot,
)
from .media_links import input_key, is_jpeg_name, output_key, outputs_expire_utc
from .runner import Runner, normalize_quality_mode
from .telemetry import capture_event, capture_exception
from .usage import record_job
from .workspace import Workspace

PREP_HQ_FILENAME = "prep_hq.mp4"
PREP_MODES = ("none", "hq")


def normalize_prep_mode(value: str | None, *, default: str = "none") -> str:
    raw = str(value or default).strip().lower()
    if raw in ("hq", "reconstruct", "reconstruct_first"):
        return "hq"
    return "none"

GALLERY_KEEP_JOBS_ENV = "VARIANT_GALLERY_KEEP_JOBS"
GALLERY_KEEP_HOURS_ENV = "VARIANT_GALLERY_KEEP_HOURS"
# Age is the default: a busy day of failed retries must not boot a good pack.
# Count cap is optional (0 = off). 0 hours disables age prune.
# 7 days so a posted clip is still on the Gallery row for Flagged / post URL.
GALLERY_KEEP_DAYS = 7
DEFAULT_GALLERY_KEEP_JOBS = 0
DEFAULT_GALLERY_KEEP_HOURS = float(GALLERY_KEEP_DAYS * 24)

PLATFORM_RESULTS = ("passed", "duplicate_reject", "flagged", "unknown")
COPY_FAILED_MSG = (
    "Processing finished, but the download package isn't ready. "
    "Retry delivery, or regenerate if that still fails."
)


def variant_on_disk(ws: Workspace, job_id: str, source_id: str, filename: str) -> bool:
    if not filename or filename != os.path.basename(filename) or filename in (".", ".."):
        return False
    return os.path.isfile(ws.variant_path(job_id, source_id, filename))


def variant_object_key(source_id: str, filename: str, variant: VariantInfo | None = None) -> str:
    if variant is not None and getattr(variant, "object_key", None):
        return str(variant.object_key)
    return output_key(source_id, filename)


def variant_in_object_store(object_store, source_id: str, filename: str,
                            variant: VariantInfo | None = None) -> bool:
    if object_store is None or not filename:
        return False
    exists = getattr(object_store, "exists", None)
    if not callable(exists):
        return False
    try:
        return bool(exists(variant_object_key(source_id, filename, variant)))
    except Exception:
        return False


def variant_ready(ws: Workspace, job_id: str, source_id: str, filename: str,
                  *, object_store=None, variant: VariantInfo | None = None) -> bool:
    if variant_on_disk(ws, job_id, source_id, filename):
        return True
    return variant_in_object_store(object_store, source_id, filename, variant)


def missing_ok_filenames(source: JobSource, ws: Workspace, job_id: str,
                         object_store=None) -> list[str]:
    missing: list[str] = []
    for v in source.variants:
        if v.status != "ok" or not v.filename:
            continue
        if not variant_ready(
            ws, job_id, source.source_id, v.filename,
            object_store=object_store, variant=v,
        ):
            missing.append(v.filename)
    return missing


def source_files_ready(source: JobSource, ws: Workspace, job_id: str,
                       object_store=None) -> int:
    return sum(
        1 for v in source.variants
        if v.status == "ok" and v.filename
        and variant_ready(
            ws, job_id, source.source_id, v.filename,
            object_store=object_store, variant=v,
        )
    )


def source_copy_status(source: JobSource, ws: Workspace, job_id: str,
                       job_state: str | None, object_store=None) -> Literal["ok", "copying", "missing"]:
    """ok = files on disk or object storage; copying = job still running; missing = GPU done, files not here."""
    if not missing_ok_filenames(source, ws, job_id, object_store=object_store):
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
    ig_media_id: str | None = None
    ig_user_id: str | None = None
    ig_insights: dict | None = None
    look_status: str | None = None
    look_mae: float | None = None
    look_src: str | None = None
    look_var: str | None = None
    caption: str | None = None
    object_key: str | None = None
    nbytes: int | None = None


@dataclass
class JobSource:
    source_id: str
    filename: str
    requested: int
    variants: list[VariantInfo] = field(default_factory=list)
    runpod_job_id: str | None = None
    planned_captions: list[str] = field(default_factory=list)
    caption_prompt: str = ""
    prep_status: str | None = None
    source_object_key: str | None = None
    drive_file_id: str | None = None

    @property
    def delivered(self) -> int:
        return sum(1 for v in self.variants if v.status == "ok")

    @property
    def shortfall(self) -> int:
        return max(0, self.requested - self.delivered)


def _clean_caption(text: str | None) -> str | None:
    cleaned = strip_internal_index_lines(text or "")
    return cleaned or None


def _caption_for(source: JobSource, index: int) -> str | None:
    caps = source.planned_captions or []
    i = int(index) - 1
    if 0 <= i < len(caps):
        return caps[i] or None
    return None


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
    created_seq: int = 0
    generate_captions: bool = False
    prep_mode: str = "none"
    prep_status: str | None = None
    telemetry: dict = field(default_factory=dict)
    outputs_expires_utc: str | None = None
    delivery_destination: str = "download"


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


def gallery_keep_jobs(environ: Mapping[str, str] | None = None) -> int:
    """Optional count cap on finished Generate jobs. 0 = no count cap (age is the default)."""
    env = os.environ if environ is None else environ
    raw = env.get(GALLERY_KEEP_JOBS_ENV, str(DEFAULT_GALLERY_KEEP_JOBS))
    try:
        return max(0, int(str(raw).strip()))
    except (TypeError, ValueError):
        return DEFAULT_GALLERY_KEEP_JOBS


def gallery_keep_hours(environ: Mapping[str, str] | None = None) -> float:
    """Hours to keep a finished Generate job. Default 7 days. 0 disables age prune."""
    env = os.environ if environ is None else environ
    raw = env.get(GALLERY_KEEP_HOURS_ENV, str(DEFAULT_GALLERY_KEEP_HOURS))
    try:
        return max(0.0, float(str(raw).strip()))
    except (TypeError, ValueError):
        return DEFAULT_GALLERY_KEEP_HOURS


_keep_from_env = gallery_keep_jobs
_hours_from_env = gallery_keep_hours


def _utc_now() -> _dt.datetime:
    return _dt.datetime.now(_dt.UTC)


def _now() -> str:
    return (_utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z"))


def _parse_utc(value: str | None) -> _dt.datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = _dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.UTC)
    return dt.astimezone(_dt.UTC)


def _variant_to_dict(v: VariantInfo) -> dict:
    return {
        "source_id": v.source_id, "index": v.index, "filename": v.filename,
        "status": v.status, "quality": v.quality, "uniqueness": v.uniqueness,
        "uniqueness_status": v.uniqueness_status, "uniqueness_metric": v.uniqueness_metric,
        "uniqueness_target": v.uniqueness_target, "preset_used": v.preset_used,
        "strength_final": v.strength_final, "escalated": v.escalated,
        "platform_result": v.platform_result, "post_url": v.post_url,
        "ig_media_id": v.ig_media_id, "ig_user_id": v.ig_user_id,
        "ig_insights": v.ig_insights,
        "look_status": v.look_status, "look_mae": v.look_mae,
        "look_src": v.look_src, "look_var": v.look_var,
        "caption": v.caption,
        "object_key": v.object_key,
        "nbytes": v.nbytes,
    }


def queue_occupies_hq(job: Job) -> bool:
    """Live GPU occupancy: standalone HQ, or reconstruct-first until prep is done."""
    if job.quality_mode == "hq":
        return True
    return job.prep_mode == "hq" and job.prep_status != "done"


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
            "prep_mode": job.prep_mode,
            "prep_status": job.prep_status,
            "state": job.state,
            "created_utc": job.created_utc,
            "count": job.count,
            "source_count": len(job.sources),
            "filenames": [s.filename for s in job.sources],
            "delivered": sum(s.delivered for s in job.sources),
            "requested": requested,
            "position": i,
        })
    hq_n = sum(1 for j in running if queue_occupies_hq(j))
    return {
        "running": len(items),
        "fast": len(items) - hq_n,
        "hq": hq_n,
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
        ig_media_id=data.get("ig_media_id") or None,
        ig_user_id=data.get("ig_user_id") or None,
        ig_insights=data.get("ig_insights") if isinstance(data.get("ig_insights"), dict) else None,
        look_status=data.get("look_status"),
        look_mae=data.get("look_mae"),
        look_src=data.get("look_src"),
        look_var=data.get("look_var"),
        caption=data.get("caption") or None,
        object_key=data.get("object_key") or None,
        nbytes=data.get("nbytes"),
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
        look_status=data.get("look_status"),
        look_mae=data.get("look_mae"),
        look_src=data.get("look_src"),
        look_var=data.get("look_var"),
    )


def _job_to_dict(job: Job) -> dict:
    return {
        "job_id": job.job_id,
        "count": job.count,
        "created_utc": job.created_utc,
        "created_seq": job.created_seq,
        "state": job.state,
        "quality_mode": job.quality_mode,
        "allow_creative_escalate": job.allow_creative_escalate,
        "generate_captions": job.generate_captions,
        "prep_mode": job.prep_mode,
        "prep_status": job.prep_status,
        "error": job.error,
        "telemetry": dict(job.telemetry or {}),
        "outputs_expires_utc": job.outputs_expires_utc,
        "delivery_destination": job.delivery_destination,
        "sources": [
            {
                "source_id": s.source_id,
                "filename": s.filename,
                "requested": s.requested,
                "runpod_job_id": s.runpod_job_id,
                "planned_captions": list(s.planned_captions or []),
                "caption_prompt": s.caption_prompt or "",
                "prep_status": s.prep_status,
                "source_object_key": s.source_object_key,
                "drive_file_id": s.drive_file_id,
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
            planned_captions=[str(c) for c in (raw.get("planned_captions") or []) if str(c).strip()],
            caption_prompt=str(raw.get("caption_prompt") or ""),
            prep_status=raw.get("prep_status"),
            source_object_key=raw.get("source_object_key") or None,
            drive_file_id=raw.get("drive_file_id") or None,
        )
        for v in raw.get("variants") or []:
            if isinstance(v, dict):
                source.variants.append(_variant_from_dict(v, sid))
        sources.append(source)
    events = []
    for raw in data.get("events") or []:
        if isinstance(raw, dict):
            events.append(_event_from_dict(raw))
    try:
        created_seq = int(data.get("created_seq") or 0)
    except (TypeError, ValueError):
        created_seq = 0
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
        created_seq=created_seq,
        generate_captions=bool(data.get("generate_captions") or False),
        prep_mode=normalize_prep_mode(data.get("prep_mode")),
        prep_status=data.get("prep_status"),
        telemetry=data.get("telemetry") if isinstance(data.get("telemetry"), dict) else {},
        outputs_expires_utc=data.get("outputs_expires_utc"),
        delivery_destination=str(data.get("delivery_destination") or "download"),
    )


def _source_finished(source: JobSource, *, ws: Workspace | None = None,
                     job_id: str | None = None, object_store=None) -> bool:
    """Done when requested slots exist and ok files are on disk or in object storage."""
    if len(source.variants) < source.requested or source.requested <= 0:
        return False
    if ws is None or not job_id:
        return True
    return not missing_ok_filenames(source, ws, job_id, object_store=object_store)


class JobStore:
    def __init__(self, workspace: Workspace, runner: Runner,
                 object_store=None, gallery_keep_jobs: int | None = None,
                 gallery_keep_hours: float | None = None,
                 keep_local_media: bool | None = None,
                 workspace_id: str | None = None,
                 drive_token_fn=None) -> None:
        self._ws = workspace
        self._runner = runner
        self._object_store = object_store
        self._workspace_id = workspace_id
        self._drive_token_fn = drive_token_fn
        # Object storage is the mailbox. Railway disk is only for local-dev /
        # FakeRunner and for tiny look JPEG posters.
        if keep_local_media is None:
            keep_local_media = object_store is None
        self._keep_local_media = bool(keep_local_media)
        keep_n = gallery_keep_jobs
        self._keep = _keep_from_env() if keep_n is None else max(0, int(keep_n))
        hours = gallery_keep_hours
        self._keep_hours = (
            _hours_from_env() if hours is None else max(0.0, float(hours))
        )
        self._seq = 0
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._done: dict[str, threading.Event] = {}
        self._source_index: dict[str, tuple[str, JobSource]] = {}
        self._cancel: dict[str, CancelToken] = {}

    def create_job(self, uploads: list[tuple[str, bytes]], count: int,
                    allow_creative_escalate: bool = True,
                    quality_mode: str = "fast",
                    generate_captions: bool = False,
                    prep_mode: str = "none",
                    caption_prompt: str = "",
                    caption_prompts: list[str] | None = None,
                    actor_email: str | None = None) -> Job:
        job_id = uuid.uuid4().hex[:12]
        sources = []
        for filename, data in uploads:
            source_id = uuid.uuid4().hex[:12]
            safe_name = os.path.basename(filename or "") or "video.mp4"
            if safe_name in (".", ".."):
                safe_name = "video.mp4"
            self._ws.save_upload(job_id, source_id, safe_name, data)
            source = JobSource(source_id=source_id, filename=safe_name, requested=count)
            sources.append(source)
        return self._start_job(
            job_id, sources, count, allow_creative_escalate, quality_mode,
            generate_captions=generate_captions, prep_mode=prep_mode,
            caption_prompt=caption_prompt, caption_prompts=caption_prompts,
            actor_email=actor_email,
        )

    def create_job_from_paths(self, paths: list[tuple[str, str]], count: int,
                               allow_creative_escalate: bool = True,
                               quality_mode: str = "fast",
                               generate_captions: bool = False,
                               prep_mode: str = "none",
                               caption_prompt: str = "",
                               caption_prompts: list[str] | None = None,
                               actor_email: str | None = None) -> Job:
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
        return self._start_job(
            job_id, sources, count, allow_creative_escalate, quality_mode,
            generate_captions=generate_captions, prep_mode=prep_mode,
            caption_prompt=caption_prompt, caption_prompts=caption_prompts,
            actor_email=actor_email,
        )

    def create_job_from_object_keys(
        self, items: list[tuple[str, str]], count: int,
        allow_creative_escalate: bool = True,
        quality_mode: str = "fast",
        generate_captions: bool = False,
        prep_mode: str = "none",
        caption_prompt: str = "",
        caption_prompts: list[str] | None = None,
        actor_email: str | None = None,
    ) -> Job:
        """Create a job from object-storage keys: [(filename, object_key), ...].

        Copies each upload key to ``inputs/{source_id}/`` without reading bytes
        through Railway when the store supports ``copy``. Local runners still
        download once so FakeRunner/ffmpeg have a path.
        """
        store = self._object_store
        if store is None:
            raise RuntimeError("object store is required for direct uploads")
        job_id = uuid.uuid4().hex[:12]
        sources = []
        for filename, key in items:
            source_id = uuid.uuid4().hex[:12]
            dest_key = input_key(source_id, filename)
            if key != dest_key:
                copy = getattr(store, "copy", None)
                if callable(copy):
                    copy(key, dest_key)
                else:
                    tmp = self._ws.source_in_path(job_id, source_id, filename)
                    store.get(key, tmp)
                    store.put(dest_key, tmp)
            needs_local = self._keep_local_media or not callable(
                getattr(self._runner, "resume_run", None),
            )
            if needs_local:
                dest = self._ws.source_in_path(job_id, source_id, filename)
                if not os.path.isfile(dest):
                    store.get(dest_key, dest)
            source = JobSource(
                source_id=source_id, filename=filename, requested=count,
                source_object_key=dest_key,
            )
            sources.append(source)
        return self._start_job(
            job_id, sources, count, allow_creative_escalate, quality_mode,
            generate_captions=generate_captions, prep_mode=prep_mode,
            caption_prompt=caption_prompt, caption_prompts=caption_prompts,
            actor_email=actor_email,
        )

    def create_job_from_drive_ids(
        self, items: list[tuple[str, str]], count: int,
        allow_creative_escalate: bool = True,
        quality_mode: str = "fast",
        generate_captions: bool = False,
        prep_mode: str = "none",
        caption_prompt: str = "",
        caption_prompts: list[str] | None = None,
        actor_email: str | None = None,
    ) -> Job:
        """Create a job from Drive file ids. RunPod downloads; Railway does not.

        items: ``[(filename, drive_file_id), ...]``
        """
        job_id = uuid.uuid4().hex[:12]
        sources = []
        for filename, drive_file_id in items:
            source_id = uuid.uuid4().hex[:12]
            sources.append(JobSource(
                source_id=source_id, filename=filename, requested=count,
                source_object_key=input_key(source_id, filename),
                drive_file_id=str(drive_file_id),
            ))
        return self._start_job(
            job_id, sources, count, allow_creative_escalate, quality_mode,
            generate_captions=generate_captions, prep_mode=prep_mode,
            caption_prompt=caption_prompt, caption_prompts=caption_prompts,
            actor_email=actor_email,
        )

    def _start_job(self, job_id: str, sources: list[JobSource], count: int,
                    allow_creative_escalate: bool, quality_mode: str = "fast",
                    generate_captions: bool = False,
                    prep_mode: str = "none",
                    caption_prompt: str = "",
                    caption_prompts: list[str] | None = None,
                    actor_email: str | None = None) -> Job:
        briefs = briefs_for_sources(
            len(sources),
            caption_prompt=caption_prompt,
            caption_prompts=caption_prompts,
        )
        for source, brief in zip(sources, briefs, strict=True):
            source.caption_prompt = brief
        if generate_captions:
            for source in sources:
                brief = (source.caption_prompt or "").strip()
                source.planned_captions = captions_for_source(
                    source.filename, source.requested, prompt=brief or None,
                )
        with self._lock:
            self._seq += 1
            created_seq = self._seq
        prep = normalize_prep_mode(prep_mode)
        quality = normalize_quality_mode(quality_mode)
        if prep == "hq":
            quality = "fast"
        created = _now()
        telemetry = {
            "workspace_id": self._workspace_id,
            "requested": count,
            "submitted_utc": created,
            "processing_charge": processing_charge_label(
                quality, count, prep_mode=prep,
            ),
            "delivery_destination": "download",
        }
        email = (actor_email or "").strip().lower()
        if email:
            telemetry["customer_email"] = email
        job = Job(job_id=job_id, count=count, created_utc=created, sources=sources,
                   allow_creative_escalate=allow_creative_escalate,
                   quality_mode=quality,
                   created_seq=created_seq,
                   generate_captions=bool(generate_captions),
                   prep_mode=prep,
                   telemetry=telemetry)
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
        self._forget_objects([source_id])
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
        source_ids = [s.source_id for s in job.sources]
        with self._lock:
            self._jobs.pop(job_id, None)
            self._cancel.pop(job_id, None)
            for source in job.sources:
                self._source_index.pop(source.source_id, None)
            ev = self._done.get(job_id)
            if ev is not None:
                ev.set()
            self._ws.remove_job(job_id)
        self._forget_objects(source_ids)
        return True

    def _forget_objects(self, source_ids: list[str]) -> None:
        """Drop R2/S3 inputs/{id}/ and outputs/{id}/ for deleted packs."""
        store = self._object_store
        delete = getattr(store, "delete_prefix", None) if store is not None else None
        if not callable(delete):
            return
        for sid in source_ids:
            if not sid or sid != os.path.basename(sid) or sid in (".", ".."):
                continue
            for kind in ("inputs", "outputs"):
                try:
                    delete(f"{kind}/{sid}/")
                except Exception as exc:
                    print(
                        f"object store delete {kind}/{sid}/ failed: "
                        f"{type(exc).__name__}: {exc}",
                        flush=True,
                    )

    def prune_finished_jobs(self) -> None:
        """Drop finished Generate jobs past the age window and/or over a count cap.

        Default is 7 days, no count cap — failed retries in a busy day must not
        boot a good pack. Running jobs are never deleted. hours=0 and keep=0
        disables. An 8-pack is one job. Object-storage MP4s expire sooner
        (VARIANT_OUTPUT_KEEP_HOURS) while job metadata remains.
        """
        self.prune_expired_outputs()
        keep = self._keep
        hours = self._keep_hours
        if keep <= 0 and hours <= 0:
            return
        now = _utc_now()
        with self._lock:
            finished = [j for j in self._jobs.values() if j.state != "running"]
            drop: set[str] = set()
            if hours > 0:
                cutoff = now - _dt.timedelta(hours=hours)
                for job in finished:
                    created = _parse_utc(job.created_utc)
                    if created is not None and created < cutoff:
                        drop.add(job.job_id)
            remain = [j for j in finished if j.job_id not in drop]
            if keep > 0 and len(remain) > keep:
                remain.sort(key=lambda j: (j.created_utc or "", j.created_seq, j.job_id))
                for job in remain[:-keep]:
                    drop.add(job.job_id)
            ids = list(drop)
        for job_id in ids:
            self.delete_job(job_id)

    def prune_expired_outputs(self) -> None:
        """Delete object-storage MP4s after outputs_expires_utc; keep job.json."""
        store = self._object_store
        if store is None:
            return
        now = _utc_now()
        with self._lock:
            jobs = [j for j in self._jobs.values() if j.state != "running"]
        for job in jobs:
            exp = _parse_utc(job.outputs_expires_utc)
            if exp is None or exp > now:
                continue
            if job.telemetry.get("outputs_deleted"):
                continue
            self._forget_objects([s.source_id for s in job.sources])
            job.telemetry = merge_telemetry(job.telemetry, outputs_deleted=True)
            self._persist(job)

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

    def _prep_hq_path(self, job_id: str, source_id: str, filename: str) -> str:
        in_dir = os.path.dirname(self._ws.source_in_path(job_id, source_id, filename))
        return os.path.join(in_dir, PREP_HQ_FILENAME)

    def _fast_in_path(self, job: Job, _source: JobSource, original: str) -> str | None:
        if job.prep_mode != "hq":
            return original
        dest = os.path.join(os.path.dirname(original), PREP_HQ_FILENAME)
        return dest if os.path.isfile(dest) else None

    def _ensure_hq_prep(
        self, job: Job, source: JobSource, in_path: str, token: CancelToken,
    ) -> str | None:
        dest = os.path.join(os.path.dirname(in_path), PREP_HQ_FILENAME)
        if source.prep_status == "done" and os.path.isfile(dest):
            return dest
        if token.is_set():
            raise JobCancelled()
        job.prep_status = "running"
        source.prep_status = "running"
        self._persist(job)
        prep_out = os.path.join(os.path.dirname(os.path.dirname(in_path)), "prep")
        os.makedirs(prep_out, exist_ok=True)

        def on_prep_event(e: VariantEvent) -> None:
            if token.runpod_job_id:
                source.runpod_job_id = token.runpod_job_id
                self._persist(job)

        try:
            result = self._runner.run(
                in_path, count=1, out_dir=prep_out,
                source_id=source.source_id, on_event=on_prep_event,
                allow_creative_escalate=job.allow_creative_escalate,
                quality_mode="hq",
                cancel_token=token,
            )
        except JobCancelled:
            source.prep_status = "failed"
            job.prep_status = "failed"
            self._persist(job)
            raise
        hero = next(
            (
                v for v in result.variants
                if v.status == "ok" and getattr(v, "path", None) and os.path.isfile(v.path)
            ),
            None,
        )
        if hero is None:
            source.prep_status = "failed"
            job.prep_status = "failed"
            if not job.error:
                job.error = "HQ reconstruct did not produce a usable file."
            self._persist(job)
            return None
        shutil.copyfile(hero.path, dest)
        source.prep_status = "done"
        source.runpod_job_id = None
        if all(s.prep_status == "done" for s in job.sources):
            job.prep_status = "done"
        self._persist(job)
        return dest

    def _record_usage(self, job: Job) -> None:
        try:
            job.telemetry = finalize_telemetry(
                job, now_utc=_now(), workspace_id=self._workspace_id,
            )
            job.outputs_expires_utc = outputs_expire_utc(
                destination=job.delivery_destination or "download",
            )
            job.telemetry["outputs_expires_utc"] = job.outputs_expires_utc
            if record_job(self._ws, job):
                props = {
                    "job_id": job.job_id,
                    "prep_mode": job.prep_mode,
                    "quality_mode": job.quality_mode,
                    "fast_copies": sum(s.delivered for s in job.sources)
                    if job.quality_mode != "hq" else 0,
                    "hq_preps": sum(
                        1 for s in job.sources if s.prep_status == "done"
                    ) if job.prep_mode == "hq" else (
                        sum(s.delivered for s in job.sources)
                        if job.quality_mode == "hq" else 0
                    ),
                    "count": job.count,
                    "source_count": len(job.sources),
                }
                for key in (
                    "workspace_id", "customer_email", "runpod_job_id", "runpod_endpoint_id",
                    "retry_count", "regen_count", "input_bytes", "output_bytes",
                    "railway_media_bytes", "delivery_destination",
                    "runpod_cost_usd", "processing_charge",
                    "submitted_utc", "started_utc", "completed_utc",
                    "first_render_utc", "hunt",
                ):
                    if job.telemetry.get(key) is not None:
                        props[key] = job.telemetry[key]
                actor = job.telemetry.get("customer_email") or job.telemetry.get("workspace_id")
                capture_event(
                    "job_completed",
                    props,
                    distinct_id=str(actor or "studio"),
                )
        except (OSError, TypeError, ValueError) as exc:
            print(f"usage {job.job_id} failed: {type(exc).__name__}: {exc}", flush=True)

    def _run_job(self, job: Job, token: CancelToken, *, skip_finished: bool = False) -> None:
        try:
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
                            look_status=e.look_status, look_mae=e.look_mae,
                            look_src=e.look_src, look_var=e.look_var,
                            caption=_caption_for(source, e.index),
                        ))
                        break
                if e.state == "rendering" and not (job.telemetry or {}).get("first_render_utc"):
                    job.telemetry = merge_telemetry(
                        job.telemetry, first_render_utc=_now(),
                    )
                    self._persist(job)
                if e.state == "looking":
                    names = [n for n in (e.look_src, e.look_var) if n and is_jpeg_name(n)]
                    if names:
                        self._pull_named_outputs(e.source_id, names)
                if token.runpod_job_id:
                    job.telemetry = merge_telemetry(
                        job.telemetry,
                        runpod_job_id=token.runpod_job_id,
                        started_utc=job.telemetry.get("started_utc") or _now(),
                    )
                if e.state in ("done", "looking") or token.runpod_job_id:
                    self._persist(job)

            for source in job.sources:
                if token.is_set():
                    raise JobCancelled()
                if skip_finished:
                    self._pull_missing_outputs(source.source_id)
                if skip_finished and _source_finished(
                    source, ws=self._ws, job_id=job.job_id,
                    object_store=self._object_store,
                ):
                    continue
                endpoint_id = getattr(self._runner, "endpoint_id", None)
                if endpoint_id:
                    job.telemetry = merge_telemetry(
                        job.telemetry, runpod_endpoint_id=endpoint_id,
                    )
                in_path = self._ws.source_in_path(job.job_id, source.source_id, source.filename)
                if (
                    not os.path.isfile(in_path)
                    and source.source_object_key
                    and self._object_store is not None
                    and self._keep_local_media
                ):
                    self._object_store.get(source.source_object_key, in_path)
                if os.path.isfile(in_path):
                    snap = source_snapshot(in_path)
                    job.telemetry = merge_telemetry(
                        job.telemetry,
                        source=snap,
                        input_bytes=(job.telemetry.get("input_bytes") or 0) + int(snap.get("bytes") or 0),
                    )
                    proxied = maybe_normalize_upload(in_path)
                    new_name = os.path.basename(proxied)
                    if new_name != source.filename:
                        source.filename = new_name
                        self._persist(job)
                    in_path = proxied
                out_dir = self._ws.source_out_dir(job.job_id, source.source_id)
                if job.prep_mode == "hq":
                    hero = self._ensure_hq_prep(job, source, in_path, token)
                    if hero is None:
                        continue
                    in_path = hero
                extra: dict = {}
                if source.drive_file_id:
                    token_fn = getattr(self, "_drive_token_fn", None)
                    wants_drive = callable(getattr(self._runner, "resume_run", None))
                    if callable(token_fn) and wants_drive:
                        extra["drive_file_id"] = source.drive_file_id
                        extra["drive_access_token"] = token_fn()
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
                        )
                    except Exception as exc:
                        print(
                            f"job {job.job_id} resume {source.runpod_job_id} failed "
                            f"({type(exc).__name__}: {exc}); not re-submitting",
                            flush=True,
                        )
                        job.telemetry = merge_telemetry(
                            job.telemetry,
                            retry_count=int(job.telemetry.get("retry_count") or 0) + 1,
                        )
                        raise
                else:
                    try:
                        result = self._runner.run(
                            in_path, count=job.count, out_dir=out_dir,
                            source_id=source.source_id, on_event=on_event,
                            allow_creative_escalate=job.allow_creative_escalate,
                            quality_mode=job.quality_mode,
                            cancel_token=token,
                            **extra,
                        )
                    except TypeError:
                        if not extra:
                            raise
                        result = self._runner.run(
                            in_path, count=job.count, out_dir=out_dir,
                            source_id=source.source_id, on_event=on_event,
                            allow_creative_escalate=job.allow_creative_escalate,
                            quality_mode=job.quality_mode,
                            cancel_token=token,
                        )
                source.variants = [
                    VariantInfo(
                        source_id=source.source_id, index=v.index, filename=v.filename,
                        status=v.status, quality=v.quality,
                        uniqueness=v.uniqueness, uniqueness_status=v.uniqueness_status,
                        uniqueness_metric=v.uniqueness_metric, uniqueness_target=v.uniqueness_target,
                        preset_used=v.preset_used, strength_final=v.strength_final,
                        escalated=v.escalated, platform_result=v.platform_result,
                        look_status=getattr(v, "look_status", None),
                        look_mae=getattr(v, "look_mae", None),
                        look_src=getattr(v, "look_src", None),
                        look_var=getattr(v, "look_var", None),
                        caption=_caption_for(source, v.index),
                        object_key=getattr(v, "object_key", None) or (
                            output_key(source.source_id, v.filename)
                            if self._object_store is not None else None
                        ),
                    )
                    for v in result.variants
                ]
                if self._object_store is not None:
                    out_bytes = 0
                    size_fn = getattr(self._object_store, "size", None)
                    for v in source.variants:
                        if not v.object_key or not callable(size_fn):
                            continue
                        try:
                            n = size_fn(v.object_key)
                        except Exception:
                            n = None
                        if n:
                            v.nbytes = int(n)
                            out_bytes += int(n)
                    if out_bytes:
                        job.telemetry = merge_telemetry(
                            job.telemetry,
                            output_bytes=(job.telemetry.get("output_bytes") or 0) + out_bytes,
                        )
                source.runpod_job_id = None
                self._persist(job)
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
                capture_exception(exc)
        finally:
            if job.job_id not in self._jobs:
                return
            job.state = "cancelled" if token.is_set() else "done"
            if job.state == "done":
                for source in job.sources:
                    self._pull_missing_outputs(source.source_id)
                self._refresh_copy_error(job)
                self._record_usage(job)
            self._persist(job)
            self.prune_finished_jobs()
            ev = self._done.get(job.job_id)
            if ev is not None:
                ev.set()

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        # Opening Gallery is the 7-day sweep — packs expire even if nobody generates.
        self.prune_finished_jobs()
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
            self._seq = max(self._seq, int(job.created_seq or 0))
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
                        ig_media_id=v.get("ig_media_id") or None,
                        ig_user_id=v.get("ig_user_id") or None,
                        ig_insights=v.get("ig_insights") if isinstance(v.get("ig_insights"), dict) else None,
                        look_status=v.get("look_status") or quality.get("look_status"),
                        look_mae=v.get("look_mae") if v.get("look_mae") is not None else quality.get("look_mae"),
                        look_src=v.get("look_src"),
                        look_var=v.get("look_var"),
                        caption=v.get("caption") or None,
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
        self.prune_finished_jobs()
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
                    out.extend(v for v in s.variants if v.status in ("best_effort", "corrupt", "uniqueness_fail"))
        return out

    def _locate(self, source_id: str) -> tuple[str, JobSource] | None:
        return self._source_index.get(source_id)

    def get_variant(self, source_id: str, index: int) -> VariantInfo | None:
        loc = self._locate(source_id)
        if loc is None:
            return None
        _, source = loc
        return next((v for v in source.variants if v.index == index), None)

    def source_job_id(self, source_id: str) -> str | None:
        loc = self._locate(source_id)
        return loc[0] if loc is not None else None

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
        if self._keep_local_media:
            self._pull_missing_outputs(source_id)
            return path if os.path.isfile(path) else None
        return None

    def _pull_named_outputs(self, source_id: str, names: list[str]) -> None:
        fetch = getattr(self._runner, "fetch_outputs", None)
        if not callable(fetch) or not names:
            return
        loc = self._locate(source_id)
        if loc is None:
            return
        job_id, _ = loc
        fetch(source_id, self._ws.source_out_dir(job_id, source_id), names)

    def _pull_missing_outputs(self, source_id: str) -> None:
        """Copy look JPEGs (and mp4s only when keep_local_media) from object storage."""
        loc = self._locate(source_id)
        if loc is None:
            return
        _, source = loc
        names: list[str] = []
        for v in source.variants:
            for n in (v.look_src, v.look_var):
                if n and is_jpeg_name(n):
                    names.append(n)
            if self._keep_local_media and v.status == "ok" and v.filename:
                names.append(v.filename)
        self._pull_named_outputs(source_id, names)

    def _refresh_copy_error(self, job: Job) -> None:
        """Surface a VA-facing error when GPU metadata is ok but files never landed."""
        if job.state != "done":
            return
        if job.error and job.error != COPY_FAILED_MSG:
            return
        missing = any(
            missing_ok_filenames(
                source, self._ws, job.job_id, object_store=self._object_store,
            )
            for source in job.sources
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
        original = self._ws.source_in_path(job_id, source_id, source.filename)
        in_path = original
        if job is not None:
            in_path = self._fast_in_path(job, source, original)
            if in_path is None:
                return source
        result = self._runner.run(
            in_path,
            count=n, out_dir=out_dir, source_id=source_id, on_event=lambda e: None,
            allow_creative_escalate=allow_creative_escalate,
            quality_mode=quality_mode,
        )
        for v in result.variants:
            source.variants.append(VariantInfo(
                source_id=source_id, index=start + v.index, filename=v.filename,
                status=v.status, quality=v.quality,
                uniqueness=v.uniqueness, uniqueness_status=v.uniqueness_status,
                uniqueness_metric=v.uniqueness_metric, uniqueness_target=v.uniqueness_target,
                preset_used=v.preset_used, strength_final=v.strength_final,
                escalated=v.escalated, platform_result=v.platform_result,
                look_status=getattr(v, "look_status", None),
                look_mae=getattr(v, "look_mae", None),
                look_src=getattr(v, "look_src", None),
                look_var=getattr(v, "look_var", None),
                caption=_caption_for(source, start + v.index),
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

    def set_caption(self, source_id: str, index: int, caption: str | None) -> VariantInfo | None:
        loc = self._locate(source_id)
        if loc is None:
            return None
        job_id, source = loc
        variant = next((v for v in source.variants if v.index == index), None)
        if variant is None:
            return None
        text = _clean_caption(caption)
        variant.caption = text
        caps = list(source.planned_captions or [])
        slot = int(index) - 1
        if slot >= 0:
            while len(caps) <= slot:
                caps.append("")
            caps[slot] = text or ""
            source.planned_captions = caps
        self._rewrite_manifest_fields(job_id, source_id, index, caption=text)
        job = self._jobs.get(job_id)
        if job is not None:
            self._persist(job)
        return variant

    def set_ig_insights(
        self,
        source_id: str,
        index: int,
        *,
        ig_media_id: str | None,
        ig_user_id: str | None,
        insights: dict | None,
        post_url: str | None = None,
    ) -> VariantInfo | None:
        loc = self._locate(source_id)
        if loc is None:
            return None
        job_id, source = loc
        variant = next((v for v in source.variants if v.index == index), None)
        if variant is None:
            return None
        variant.ig_media_id = ig_media_id
        variant.ig_user_id = ig_user_id
        variant.ig_insights = insights
        fields: dict[str, object] = {
            "ig_media_id": ig_media_id,
            "ig_user_id": ig_user_id,
            "ig_insights": insights,
        }
        if post_url and not variant.post_url:
            variant.post_url = post_url
            fields["post_url"] = post_url
        self._rewrite_manifest_fields(job_id, source_id, index, **fields)
        job = self._jobs.get(job_id)
        if job is not None:
            self._persist(job)
        return variant

    def rewrite_captions(self, source_id: str, prompt: str | None = None) -> JobSource | None:
        """Replace every copy's caption. Videos stay put."""
        loc = self._locate(source_id)
        if loc is None:
            return None
        job_id, source = loc
        brief = (prompt or source.caption_prompt or "").strip()
        if not brief:
            for variant in source.variants:
                cleaned = _clean_caption(variant.caption)
                if cleaned:
                    brief = cleaned
                    break
        if not brief:
            brief = brief_from_filename(source.filename)
        n = max(int(source.requested), len(source.variants), 1)
        source.caption_prompt = brief
        source.planned_captions = captions_for_source(
            source.filename,
            n,
            prompt=brief,
            avoid=list(source.planned_captions or []),
        )
        for variant in source.variants:
            variant.caption = _caption_for(source, variant.index)
            self._rewrite_manifest_fields(job_id, source_id, variant.index, caption=variant.caption)
        job = self._jobs.get(job_id)
        if job is not None:
            job.generate_captions = True
            self._persist(job)
        return source

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
        if not self._keep_local_media:
            # Object-storage jobs: browser downloads via signed URLs, not a
            # Railway-built zip streamed through the web service.
            return None
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
