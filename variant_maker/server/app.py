"""FastAPI control-plane app."""
from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from .destinations import Destination, DestinationError, DestinationStore, probe_folder_writable
from .drive_config import resolve_drive_status
from .drive_exports import (ExportError, ExportJob, ExportRunner, ExportStore, VariantRef,
                            build_export_files)
from .drive_urls import DriveUrlError, parse_folder_id
from .events import event_to_dict
from .jobs import JobSource, JobStore
from .models import (CreateJobResponse, DestinationCreateIn, DestinationOut, DestinationUpdateIn,
                     DiagnosticsItem, DriveStatusOut, ExportCreateIn, ExportFileOut, ExportJobOut,
                     JobDetail, JobSummary, PlatformResultIn, SourceOut, VariantOut)
from .runner import LocalRunner
from .workspace import Workspace
from variant_maker.farm.drive import DriveClient


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


def _destination_out(d: Destination) -> DestinationOut:
    return DestinationOut(id=d.id, name=d.name, folder_id=d.folder_id, auth_mode=d.auth_mode)


def _export_job_out(job: ExportJob) -> ExportJobOut:
    return ExportJobOut(
        export_id=job.export_id, destination_id=job.destination_id, folder_id=job.folder_id,
        state=job.state, created_utc=job.created_utc,
        files=[ExportFileOut(source_id=f.source_id, index=f.index, filename=f.filename,
                             status=f.status, error=f.error, drive_file_id=f.drive_file_id)
               for f in job.files],
    )


def _build_drive_client(sa_json_path: str) -> DriveClient:
    from variant_maker.farm.drive import GoogleDrive
    return GoogleDrive(service_account_json=sa_json_path)


def _resolve_folder_id(folder_url: str) -> str:
    """`parse_folder_id`'s bare-id heuristic requires 10+ chars (real Drive ids are
    long); fall back to treating any non-URL, non-file-link token as a literal id and
    let the write-probe be the real check, so short test-double ids still resolve."""
    s = (folder_url or "").strip()
    try:
        return parse_folder_id(s)
    except DriveUrlError:
        if s and "://" not in s and "/" not in s:
            return s
        raise


def create_app(store: JobStore | None = None, *, drive: DriveClient | None = None,
                sa_json_path: str | None = None) -> FastAPI:
    if store is None:
        store = JobStore(Workspace("./.vmdata"), LocalRunner())
    app = FastAPI(title="variant-maker control plane")
    app.state.store = store

    drive_info = resolve_drive_status(sa_json_path)
    if drive is None and drive_info.status == "ready":
        drive = _build_drive_client(sa_json_path)
    app.state.drive = drive
    app.state.drive_info = drive_info
    app.state.destinations = DestinationStore(store._ws.destinations_path())
    app.state.exports = ExportStore(store._ws.exports_dir())

    def _require_drive() -> None:
        if app.state.drive is None or app.state.drive_info.status != "ready":
            raise HTTPException(status_code=503, detail=app.state.drive_info.message)

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

    @app.get("/api/drive/status", response_model=DriveStatusOut)
    def drive_status() -> DriveStatusOut:
        info = app.state.drive_info
        return DriveStatusOut(status=info.status, sa_email=info.sa_email, message=info.message)

    @app.get("/api/drive/destinations", response_model=list[DestinationOut])
    def list_destinations() -> list[DestinationOut]:
        return [_destination_out(d) for d in app.state.destinations.list()]

    @app.post("/api/drive/destinations", status_code=201, response_model=DestinationOut)
    def create_destination(body: DestinationCreateIn) -> DestinationOut:
        _require_drive()
        try:
            folder_id = _resolve_folder_id(body.folder_url)
        except DriveUrlError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        try:
            probe_folder_writable(app.state.drive, folder_id, sa_email=app.state.drive_info.sa_email)
        except DestinationError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        dest = app.state.destinations.create(name=body.name, folder_id=folder_id)
        return _destination_out(dest)

    @app.patch("/api/drive/destinations/{dest_id}", response_model=DestinationOut)
    def update_destination(dest_id: str, body: DestinationUpdateIn) -> DestinationOut:
        _require_drive()
        existing = app.state.destinations.get(dest_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="destination not found")
        folder_id = None
        if body.folder_url is not None:
            try:
                folder_id = _resolve_folder_id(body.folder_url)
            except DriveUrlError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
            if folder_id != existing.folder_id:
                try:
                    probe_folder_writable(app.state.drive, folder_id,
                                          sa_email=app.state.drive_info.sa_email)
                except DestinationError as e:
                    raise HTTPException(status_code=400, detail=str(e)) from e
        updated = app.state.destinations.update(dest_id, name=body.name, folder_id=folder_id)
        return _destination_out(updated)

    @app.delete("/api/drive/destinations/{dest_id}", status_code=204)
    def delete_destination(dest_id: str) -> None:
        _require_drive()
        if not app.state.destinations.delete(dest_id):
            raise HTTPException(status_code=404, detail="destination not found")
        return None

    @app.post("/api/drive/destinations/{dest_id}/test")
    def test_destination(dest_id: str) -> dict:
        _require_drive()
        dest = app.state.destinations.get(dest_id)
        if dest is None:
            raise HTTPException(status_code=404, detail="destination not found")
        try:
            probe_folder_writable(app.state.drive, dest.folder_id,
                                  sa_email=app.state.drive_info.sa_email)
        except DestinationError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {"ok": True}

    @app.post("/api/drive/exports", status_code=201, response_model=ExportJobOut)
    def create_export(body: ExportCreateIn) -> ExportJobOut:
        _require_drive()
        dest = app.state.destinations.get(body.destination_id)
        if dest is None:
            raise HTTPException(status_code=404, detail="destination not found")
        refs = [VariantRef(source_id=v.source_id, index=v.index) for v in body.variants]
        try:
            files = build_export_files(store, refs)
        except ExportError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        job = app.state.exports.create(destination_id=dest.id, folder_id=dest.folder_id, files=files)
        ExportRunner(app.state.drive, app.state.exports).start(job)
        return _export_job_out(job)

    @app.get("/api/drive/exports/{export_id}", response_model=ExportJobOut)
    def get_export(export_id: str) -> ExportJobOut:
        job = app.state.exports.get(export_id)
        if job is None:
            raise HTTPException(status_code=404, detail="export not found")
        return _export_job_out(job)

    @app.post("/api/drive/exports/{export_id}/retry", response_model=ExportJobOut)
    def retry_export(export_id: str) -> ExportJobOut:
        _require_drive()
        try:
            job = ExportRunner(app.state.drive, app.state.exports).retry_failed(export_id)
        except ExportError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return _export_job_out(job)

    return app
