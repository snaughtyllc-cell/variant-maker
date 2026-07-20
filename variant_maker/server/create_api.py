"""Create-mode FastAPI router + in-memory job store.

Self-contained so Spoof progress WIP in app.py is untouched until a one-line mount.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from .create_models import (
    CreateJobDetail,
    CreateJobResponse,
    CreateStillOut,
    PromptOut,
)
from .workspace import Workspace

ALLOWED_ASPECTS = ("9:16", "1:1", "16:9")


class CreateRunnerLike(Protocol):
    def run(
        self,
        *,
        job_id: str,
        brief: str,
        aspect: str,
        count: int,
        face_refs: list[tuple[str, bytes]],
        identities: list[str],
        out_dir: str,
        on_event,
    ) -> list[dict]: ...


def _now() -> str:
    return (_dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)
            .isoformat().replace("+00:00", "Z"))


@dataclass
class CreateStillInfo:
    index: int
    filename: str
    handoff_filename: str
    status: str


@dataclass
class CreateJob:
    job_id: str
    brief: str
    aspect: str
    count: int
    created_utc: str
    identities: list[str] = field(default_factory=list)
    state: str = "running"
    events: list[dict] = field(default_factory=list)
    stills: list[CreateStillInfo] = field(default_factory=list)
    prompt: dict | None = None
    error: str | None = None


class CreateJobStore:
    """In-memory Create jobs; parallel to Spoof JobStore, separate namespace."""

    def __init__(self, workspace: Workspace, runner: CreateRunnerLike) -> None:
        self._ws = workspace
        self._runner = runner
        self._jobs: dict[str, CreateJob] = {}
        self._lock = threading.Lock()
        self._done: dict[str, threading.Event] = {}

    def create_job(
        self,
        *,
        brief: str,
        aspect: str,
        count: int,
        face_refs: list[tuple[str, bytes]],
        identities: list[str] | None = None,
    ) -> CreateJob:
        if aspect not in ALLOWED_ASPECTS:
            raise ValueError(f"aspect must be one of {ALLOWED_ASPECTS}")
        if count < 1 or count > 4:
            raise ValueError("count must be 1..4")
        if not brief.strip():
            raise ValueError("brief is required")
        if not face_refs:
            raise ValueError("at least one face_ref is required")

        job_id = uuid.uuid4().hex[:12]
        job_dir = os.path.join(self._ws.root, "create", job_id)
        in_dir = os.path.join(job_dir, "in")
        out_dir = os.path.join(job_dir, "out")
        os.makedirs(in_dir, exist_ok=True)
        os.makedirs(out_dir, exist_ok=True)

        saved_refs: list[tuple[str, bytes]] = []
        for filename, data in face_refs:
            safe = os.path.basename(filename) or "face.jpg"
            path = os.path.join(in_dir, safe)
            with open(path, "wb") as f:
                f.write(data)
            saved_refs.append((safe, data))

        job = CreateJob(
            job_id=job_id,
            brief=brief.strip(),
            aspect=aspect,
            count=count,
            created_utc=_now(),
            identities=list(identities or ["creator"]),
        )
        with self._lock:
            self._jobs[job_id] = job
            self._done[job_id] = threading.Event()
        threading.Thread(
            target=self._run_job,
            args=(job, saved_refs, out_dir),
            daemon=True,
        ).start()
        return job

    def _run_job(self, job: CreateJob, face_refs: list[tuple[str, bytes]], out_dir: str) -> None:
        try:
            def on_event(e: dict) -> None:
                job.events.append(e)
                if e.get("state") == "expanded" and e.get("prompt"):
                    job.prompt = e["prompt"]
                if e.get("state") == "done" and e.get("filename"):
                    if any(s.index == e["index"] for s in job.stills):
                        return
                    job.stills.append(CreateStillInfo(
                        index=int(e["index"]),
                        filename=e["filename"],
                        handoff_filename=e.get("handoff_filename") or "",
                        status=e.get("status") or "ok",
                    ))

            self._runner.run(
                job_id=job.job_id,
                brief=job.brief,
                aspect=job.aspect,
                count=job.count,
                face_refs=face_refs,
                identities=job.identities,
                out_dir=out_dir,
                on_event=on_event,
            )
        except Exception as exc:  # noqa: BLE001 — surface to clients via job.error
            job.error = str(exc)
            job.events.append({"state": "error", "job_id": job.job_id, "error": str(exc)})
        finally:
            job.state = "done"
            if not job.events or job.events[-1].get("state") != "job-done":
                job.events.append({"state": "job-done", "job_id": job.job_id})
            self._done[job.job_id].set()

    def get(self, job_id: str) -> CreateJob | None:
        return self._jobs.get(job_id)

    def wait(self, job_id: str, timeout: float = 30.0) -> bool:
        ev = self._done.get(job_id)
        return ev.wait(timeout) if ev else False

    def file_path(self, job_id: str, filename: str) -> str | None:
        safe = os.path.basename(filename)
        path = os.path.join(self._ws.root, "create", job_id, "out", safe)
        return path if os.path.isfile(path) else None


def _still_out(job_id: str, s: CreateStillInfo) -> CreateStillOut:
    return CreateStillOut(
        index=s.index,
        filename=s.filename,
        handoff_filename=s.handoff_filename,
        status=s.status,
        file_url=f"/api/create/jobs/{job_id}/files/{s.filename}",
        handoff_url=f"/api/create/jobs/{job_id}/files/{s.handoff_filename}",
    )


def _detail(job: CreateJob) -> CreateJobDetail:
    prompt = PromptOut(**job.prompt) if job.prompt else None
    return CreateJobDetail(
        job_id=job.job_id,
        state=job.state,
        brief=job.brief,
        aspect=job.aspect,  # type: ignore[arg-type]
        count=job.count,
        created_utc=job.created_utc,
        stills=[_still_out(job.job_id, s) for s in job.stills],
        prompt=prompt,
        error=job.error,
        identities=list(job.identities),
    )


def build_create_router(store: CreateJobStore) -> APIRouter:
    router = APIRouter(tags=["create"])

    @router.post("/api/create/jobs", status_code=201, response_model=CreateJobResponse)
    async def create_job(
        brief: str = Form(...),
        aspect: str = Form("9:16"),
        count: int = Form(1),
        identities: str = Form("creator"),
        face_refs: list[UploadFile] = File(...),
    ) -> CreateJobResponse:
        if count < 1 or count > 4:
            raise HTTPException(status_code=422, detail="count must be 1..4")
        if aspect not in ALLOWED_ASPECTS:
            raise HTTPException(status_code=422, detail=f"aspect must be one of {ALLOWED_ASPECTS}")
        if not face_refs:
            raise HTTPException(status_code=422, detail="at least one face_ref is required")
        uploads = [(f.filename or f"face_{i}.jpg", await f.read()) for i, f in enumerate(face_refs)]
        if not any(data for _, data in uploads):
            raise HTTPException(status_code=422, detail="face_refs must not be empty")
        idents = [p.strip() for p in identities.split(",") if p.strip()] or ["creator"]
        try:
            job = store.create_job(
                brief=brief,
                aspect=aspect,
                count=count,
                face_refs=uploads,
                identities=idents,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return CreateJobResponse(
            job_id=job.job_id,
            state=job.state,
            brief=job.brief,
            aspect=job.aspect,  # type: ignore[arg-type]
            count=job.count,
            created_utc=job.created_utc,
        )

    @router.get("/api/create/jobs/{job_id}", response_model=CreateJobDetail)
    def get_job(job_id: str) -> CreateJobDetail:
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="create job not found")
        return _detail(job)

    @router.get("/api/create/jobs/{job_id}/events")
    async def job_events(job_id: str):
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="create job not found")

        async def gen():
            sent = 0
            while True:
                while sent < len(job.events):
                    yield {"data": json.dumps(job.events[sent])}
                    sent += 1
                if job.state == "done" and sent >= len(job.events):
                    # ensure terminal event even if runner forgot job-done
                    if not job.events or job.events[-1].get("state") != "job-done":
                        yield {"data": json.dumps({"state": "job-done", "job_id": job_id})}
                    return
                await asyncio.sleep(0.1)

        return EventSourceResponse(gen())

    @router.get("/api/create/jobs/{job_id}/files/{filename}")
    def job_file(job_id: str, filename: str):
        path = store.file_path(job_id, filename)
        if path is None:
            raise HTTPException(status_code=404, detail="file not found")
        media = "video/mp4" if filename.lower().endswith(".mp4") else "image/png"
        return FileResponse(path, media_type=media)

    return router


class _UnconfiguredCreateRunner:
    """Placeholder when PROMPT_LLM_API_KEY is unset — routes still mount."""

    def run(self, **_kwargs):
        raise RuntimeError(
            "Create mode not configured: set PROMPT_LLM_API_KEY "
            "(and COMFY_URL / COMFY_WORKFLOW_PATH as needed)"
        )


def mount_create_routes(app: FastAPI, store: CreateJobStore | None = None) -> CreateJobStore:
    """One-line wire-up for create_app(); returns the store for tests."""
    if store is None:
        from .comfy_client import HttpComfyClient
        from .create_runner import CreateRunner
        from .prompt_director import HttpPromptDirector

        ws = Workspace(os.environ.get("VM_DATA_DIR", "./.vmdata"))
        if os.environ.get("PROMPT_LLM_API_KEY"):
            runner: CreateRunnerLike = CreateRunner(
                director=HttpPromptDirector.from_env(),
                comfy=HttpComfyClient.from_env(),
            )
        else:
            runner = _UnconfiguredCreateRunner()
        store = CreateJobStore(ws, runner)
    app.include_router(build_create_router(store))
    app.state.create_store = store
    return store
