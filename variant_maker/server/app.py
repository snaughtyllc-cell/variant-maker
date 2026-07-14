"""FastAPI control-plane app."""
from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from .events import event_to_dict
from .jobs import JobSource, JobStore
from .models import (CreateJobResponse, DiagnosticsItem, JobDetail, JobSummary,
                     PlatformResultIn, SourceOut, VariantOut)
from .runner import LocalRunner
from .workspace import Workspace


def _variant_out(source_id: str, v) -> VariantOut:
    return VariantOut(
        index=v.index, filename=v.filename, status=v.status, quality=v.quality,
        file_url=f"/api/variants/{source_id}/{v.filename}",
        uniqueness=v.uniqueness, uniqueness_status=v.uniqueness_status,
        uniqueness_metric=v.uniqueness_metric, uniqueness_target=v.uniqueness_target,
        preset_used=v.preset_used, strength_final=v.strength_final,
        escalated=v.escalated, platform_result=v.platform_result,
    )


def _source_out(s: JobSource, *, ok_only: bool) -> SourceOut:
    variants = [v for v in s.variants if (v.status == "ok" or not ok_only)]
    return SourceOut(
        source_id=s.source_id, filename=s.filename, requested=s.requested,
        delivered=s.delivered, shortfall=s.shortfall,
        variants=[_variant_out(s.source_id, v) for v in variants],
    )


def create_app(store: JobStore | None = None) -> FastAPI:
    if store is None:
        store = JobStore(Workspace("./.vmdata"), LocalRunner())
    app = FastAPI(title="variant-maker control plane")
    app.state.store = store

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/api/jobs", status_code=201, response_model=CreateJobResponse)
    async def create_job(files: list[UploadFile], count: int = Form(...),
                          allow_creative_escalate: bool = Form(True)) -> CreateJobResponse:
        uploads = [(f.filename or "video.mp4", await f.read()) for f in files]
        job = store.create_job(uploads, count=count, allow_creative_escalate=allow_creative_escalate)
        return CreateJobResponse(job_id=job.job_id,
                                 sources=[_source_out(s, ok_only=True) for s in job.sources])

    @app.get("/api/jobs", response_model=list[JobSummary])
    def list_jobs() -> list[JobSummary]:
        return [JobSummary(job_id=j.job_id, count=j.count, created_utc=j.created_utc,
                           state=j.state, source_count=len(j.sources))
                for j in store.list()]

    @app.get("/api/jobs/{job_id}", response_model=JobDetail)
    def get_job(job_id: str) -> JobDetail:
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return JobDetail(job_id=job.job_id, count=job.count, created_utc=job.created_utc,
                         state=job.state, sources=[_source_out(s, ok_only=True) for s in job.sources])

    @app.get("/api/jobs/{job_id}/events")
    async def job_events(job_id: str):
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")

        async def gen():
            sent = 0
            while True:
                # drain newly-appended events from the in-memory log
                while sent < len(job.events):
                    yield {"data": json.dumps(event_to_dict(job.events[sent]))}
                    sent += 1
                if job.state == "done" and sent >= len(job.events):
                    yield {"data": json.dumps({"state": "job-done"})}
                    return
                await asyncio.sleep(0.1)

        return EventSourceResponse(gen())

    @app.get("/api/gallery", response_model=list[SourceOut])
    def gallery() -> list[SourceOut]:
        return [_source_out(s, ok_only=True) for s in store.gallery()]

    @app.get("/api/diagnostics", response_model=list[DiagnosticsItem])
    def diagnostics() -> list[DiagnosticsItem]:
        return [DiagnosticsItem(source_id=v.source_id, index=v.index, filename=v.filename,
                                status=v.status, quality=v.quality)
                for v in store.diagnostics()]

    @app.get("/api/variants/{source_id}/{filename}")
    def variant_file(source_id: str, filename: str):
        path = store.find_variant(source_id, filename)
        if path is None:
            raise HTTPException(status_code=404, detail="variant not found")
        return FileResponse(path, media_type="video/mp4")

    @app.get("/api/sources/{source_id}/source")
    def source_file(source_id: str):
        path = store.source_file(source_id)
        if path is None:
            raise HTTPException(status_code=404, detail="source not found")
        return FileResponse(path, media_type="video/mp4")

    @app.post("/api/sources/{source_id}/regenerate", response_model=SourceOut)
    def regenerate(source_id: str, n: int = Form(...)) -> SourceOut:
        source = store.regenerate(source_id, n)
        if source is None:
            raise HTTPException(status_code=404, detail="source not found")
        return _source_out(source, ok_only=True)

    @app.post("/api/variants/{source_id}/{index}/platform-result", response_model=VariantOut)
    def set_platform_result(source_id: str, index: int, body: PlatformResultIn) -> VariantOut:
        variant = store.set_platform_result(source_id, index, body.result)
        if variant is None:
            raise HTTPException(status_code=404, detail="variant not found")
        return _variant_out(source_id, variant)

    @app.get("/api/sources/{source_id}/zip")
    def source_zip(source_id: str):
        path = store.zip_ok_variants(source_id)
        if path is None:
            raise HTTPException(status_code=404, detail="no ok variants for source")
        return FileResponse(path, media_type="application/zip",
                            filename=f"{source_id}_variants.zip")

    return app
