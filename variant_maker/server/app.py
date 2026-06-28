"""FastAPI control-plane app."""
from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI, Form, HTTPException, UploadFile
from sse_starlette.sse import EventSourceResponse

from .events import event_to_dict
from .jobs import JobSource, JobStore
from .models import CreateJobResponse, JobDetail, JobSummary, SourceOut, VariantOut
from .runner import LocalRunner
from .workspace import Workspace


def _source_out(s: JobSource, *, ok_only: bool) -> SourceOut:
    variants = [v for v in s.variants if (v.status == "ok" or not ok_only)]
    return SourceOut(
        source_id=s.source_id, filename=s.filename, requested=s.requested,
        delivered=s.delivered, shortfall=s.shortfall,
        variants=[
            VariantOut(index=v.index, filename=v.filename, status=v.status, quality=v.quality,
                       file_url=f"/api/variants/{s.source_id}/{v.filename}")
            for v in variants
        ],
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
    async def create_job(files: list[UploadFile], count: int = Form(...)) -> CreateJobResponse:
        uploads = [(f.filename or "video.mp4", await f.read()) for f in files]
        job = store.create_job(uploads, count=count)
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

    return app
