"""FastAPI control-plane app."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import threading
import traceback
import uuid
from typing import Any, Callable, Mapping

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sse_starlette.sse import EventSourceResponse

from .captions import CaptionError, CaptionStore, split_caption_bank
from .destinations import Destination, DestinationError, DestinationStore, probe_folder_writable
from .drive_config import (
    ENV_OAUTH_CLIENT_ID,
    ENV_OAUTH_CLIENT_SECRET,
    ENV_OAUTH_REDIRECT_URI,
    resolve_drive_status,
)
from .drive_exports import (ExportError, ExportJob, ExportRunner, ExportStore, VariantRef,
                            build_export_files)
from .drive_oauth import (
    OAuthPendingStore,
    OAuthTokenStore,
    build_authorization_url,
    exchange_code_for_token,
    fetch_connected_email,
    new_oauth_state,
    public_request_base,
    resolve_redirect_uri,
    studio_origin_from_redirect_uri,
)
from .drive_urls import DriveUrlError, parse_folder_id
from .drop_ledger import (
    ensure_ledger,
    list_job_ids_on_disk,
    load_manifest_rows,
    resolve_sheet_id,
    spreadsheet_url,
    sync_rows,
    update_platform_result_cell,
    write_sheet_id_file,
)
from .events import event_to_dict
from .jobs import (
    Job, JobSource, JobStore, source_copy_status, source_files_ready, variant_on_disk,
)
from .models import (CreateJobResponse, DestinationCreateIn, DestinationOut, DestinationUpdateIn,
                     DiagnosticsItem, DriveStatusOut, DriveVideoOut, DriveVideosOut,
                     DropLedgerEnsureOut, DropLedgerStatusOut, DropLedgerSyncIn, DropLedgerSyncOut,
                     ExportCreateIn, ExportFileOut, ExportJobOut, InFlightOut, JobDetail,
                     JobEventsSnapshot, JobFromDriveIn, JobSummary, PlatformResultIn, SourceOut,
                     VariantOut, WorkflowCreateIn, WorkflowOut, WorkflowSummaryOut, WorkflowUpdateIn,
                     CaptionAdvanceIn, CaptionBankFolderOut, CaptionBankOut, CaptionBulkIn,
                     CaptionCreateIn, CaptionFolderCreateIn, CaptionOut, CaptionPreviewOut)
from .runner import LocalRunner
from .sheets import GoogleSheets, SheetsClient
from .workflow_runner import tick_workflow
from .workflows import Workflow, WorkflowError, WorkflowStore
from .workspace import Workspace
from variant_maker.farm.drive import DriveClient, is_video_file
from variant_maker.farm.ledger import Ledger

_IN_FLIGHT_STATES = frozenset({"rendering", "checking", "rerolling", "uniqueness", "escalating"})
_UPLOAD_META: dict[str, dict] = {}

ExchangeFn = Callable[..., dict[str, Any]]
FetchEmailFn = Callable[[dict[str, Any]], str | None]


def _variant_out(source_id: str, v, *, file_ready: bool = True) -> VariantOut:
    return VariantOut(
        index=v.index, filename=v.filename, status=v.status, quality=v.quality,
        file_url=f"/api/variants/{source_id}/{v.filename}",
        uniqueness=v.uniqueness, uniqueness_status=v.uniqueness_status,
        uniqueness_metric=v.uniqueness_metric, uniqueness_target=v.uniqueness_target,
        preset_used=v.preset_used, strength_final=v.strength_final,
        escalated=v.escalated, platform_result=v.platform_result,
        file_ready=file_ready,
    )


def _in_flight(job: Job | None, source_id: str) -> InFlightOut | None:
    if job is None:
        return None
    # A finished job must not keep "v01 rendering" — last event is often rendering
    # when RunPod kills HQ at the 20-minute cap.
    if job.state in ("done", "cancelled"):
        return None
    for e in reversed(job.events):
        if e.source_id != source_id:
            continue
        if e.state in _IN_FLIGHT_STATES:
            return InFlightOut(
                index=e.index, state=e.state, attempt=e.attempt, max_attempts=e.max_attempts,
            )
        if e.state == "done":
            return None
    return None


def _source_out(s: JobSource, *, ok_only: bool, job: Job | None = None,
                ws: Workspace | None = None) -> SourceOut:
    variants = [v for v in s.variants if (v.status == "ok" or not ok_only)]
    failed = sum(1 for v in s.variants if v.status in ("best_effort", "corrupt"))
    job_id = job.job_id if job is not None else None
    files_ready = (
        source_files_ready(s, ws, job_id) if ws is not None and job_id else s.delivered
    )
    copy_status = (
        source_copy_status(s, ws, job_id, job.state if job is not None else None)
        if ws is not None and job_id else "ok"
    )
    return SourceOut(
        source_id=s.source_id, filename=s.filename, requested=s.requested,
        delivered=s.delivered, shortfall=s.shortfall,
        variants=[
            _variant_out(
                s.source_id, v,
                file_ready=(
                    variant_on_disk(ws, job_id, s.source_id, v.filename)
                    if ws is not None and job_id else True
                ),
            )
            for v in variants
        ],
        in_flight=_in_flight(job, s.source_id),
        job_state=job.state if job is not None else None,
        failed=failed,
        created_utc=job.created_utc if job is not None else None,
        files_ready=files_ready,
        copy_status=copy_status,
    )


def _destination_out(d: Destination) -> DestinationOut:
    return DestinationOut(id=d.id, name=d.name, folder_id=d.folder_id, auth_mode=d.auth_mode)


def _workflow_summary_out(raw: dict | None) -> WorkflowSummaryOut | None:
    if not raw:
        return None
    return WorkflowSummaryOut(
        queued=int(raw.get("queued") or 0),
        exported=int(raw.get("exported") or 0),
        skipped=int(raw.get("skipped") or 0),
        failed=int(raw.get("failed") or 0),
        running=int(raw.get("running") or 0),
        job_ids=list(raw.get("job_ids") or []),
        error=raw.get("error"),
    )


def _workflow_out(w: Workflow) -> WorkflowOut:
    return WorkflowOut(
        id=w.id,
        name=w.name,
        inbox_destination_id=w.inbox_destination_id,
        output_destination_id=w.output_destination_id,
        count=w.count,
        quality_mode=w.quality_mode,
        allow_creative_escalate=w.allow_creative_escalate,
        enabled=w.enabled,
        poll_seconds=w.poll_seconds,
        last_sweep_at=w.last_sweep_at,
        last_summary=_workflow_summary_out(w.last_summary),
        auto_caption=w.auto_caption,
        caption_bank_id=w.caption_bank_id or None,
    )


def _caption_bank_payload(store: CaptionStore, bank_id: str | None = None) -> CaptionBankOut:
    meta = store.bank_meta(bank_id)
    return CaptionBankOut(
        cursor=meta.cursor,
        items=[CaptionOut(id=c.id, text=c.text) for c in store.list(meta.id)],
        bank_id=meta.id,
        bank_name=meta.name,
        count=meta.count,
        remaining=meta.remaining,
        low=meta.low,
        is_default=meta.is_default,
    )


def _caption_folder_out(meta) -> CaptionBankFolderOut:
    return CaptionBankFolderOut(
        id=meta.id,
        name=meta.name,
        is_default=meta.is_default,
        count=meta.count,
        remaining=meta.remaining,
        cursor=meta.cursor,
        low=meta.low,
    )


def _export_job_out(job: ExportJob) -> ExportJobOut:
    return ExportJobOut(
        export_id=job.export_id, destination_id=job.destination_id, folder_id=job.folder_id,
        state=job.state, created_utc=job.created_utc,
        files=[ExportFileOut(source_id=f.source_id, index=f.index, filename=f.filename,
                             status=f.status, error=f.error, drive_file_id=f.drive_file_id)
               for f in job.files],
    )


def _drive_status_out(info) -> DriveStatusOut:
    return DriveStatusOut(
        status=info.status,
        sa_email=info.sa_email,
        message=info.message,
        auth_mode=info.auth_mode,
        connected_email=info.connected_email,
        oauth_available=info.oauth_available,
    )


def _build_drive_client(*, sa_json_path: str | None = None,
                        oauth_token_path: str | None = None) -> DriveClient:
    from variant_maker.farm.drive import GoogleDrive
    if oauth_token_path:
        return GoogleDrive(oauth_token=oauth_token_path)
    if sa_json_path:
        return GoogleDrive(service_account_json=sa_json_path)
    raise ValueError("need sa_json_path or oauth_token_path")


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


def create_app(
    store: JobStore | None = None,
    *,
    drive: DriveClient | None = None,
    sheets: SheetsClient | None = None,
    sa_json_path: str | None = None,
    oauth_token_path: str | None = None,
    oauth_environ: Mapping[str, str] | None = None,
    oauth_exchange: ExchangeFn | None = None,
    oauth_fetch_email: FetchEmailFn | None = None,
    hydrate: bool = True,
    enable_workflow_poller: bool = False,
) -> FastAPI:
    if store is None:
        store = JobStore(Workspace("./.vmdata"), LocalRunner())
    if hydrate:
        store.hydrate_from_disk()
    app = FastAPI(title="variant-maker control plane")
    app.state.store = store

    oauth_env: Mapping[str, str] = oauth_environ if oauth_environ is not None else os.environ
    if oauth_token_path is None:
        oauth_token_path = store._ws.oauth_token_path()
    token_store = OAuthTokenStore(oauth_token_path)
    pending_store = OAuthPendingStore(store._ws.oauth_pending_path())
    app.state.oauth_token_store = token_store
    app.state.oauth_pending = pending_store
    app.state.oauth_environ = oauth_env
    app.state.oauth_exchange = oauth_exchange or exchange_code_for_token
    app.state.oauth_fetch_email = oauth_fetch_email or fetch_connected_email
    drop_sheet_path = store._ws.drop_sheet_config_path()

    # Explicit "" means "no SA" (tests); None means fall through to env.
    sa_arg = None if sa_json_path in (None, "") else sa_json_path
    drive_info = resolve_drive_status(
        sa_arg,
        oauth_token_path=oauth_token_path,
        environ=oauth_env if oauth_environ is not None else None,
    )
    if sa_json_path == "":
        drive_info = resolve_drive_status(
            None, oauth_token_path=oauth_token_path, environ=oauth_env,
        )

    if drive is None and drive_info.status == "ready":
        if drive_info.auth_mode == "oauth":
            drive = _build_drive_client(oauth_token_path=oauth_token_path)
        elif sa_arg:
            drive = _build_drive_client(sa_json_path=sa_arg)
        else:
            from .drive_config import ENV_SA_JSON
            env_sa = oauth_env.get(ENV_SA_JSON) if oauth_environ is not None else os.environ.get(ENV_SA_JSON)
            if env_sa:
                drive = _build_drive_client(sa_json_path=env_sa)

    if sheets is None and drive_info.status == "ready" and drive_info.auth_mode == "oauth":
        try:
            sheets = GoogleSheets(oauth_token=oauth_token_path)
        except Exception:
            sheets = None

    app.state.drive = drive
    app.state.sheets = sheets
    app.state.drive_info = drive_info
    app.state.destinations = DestinationStore(store._ws.destinations_path())
    app.state.exports = ExportStore(store._ws.exports_dir())
    app.state.workflows = WorkflowStore(store._ws.workflows_path())
    app.state.captions = CaptionStore(store._ws.captions_path())
    app.state.workflow_tick_lock = threading.Lock()

    def _refresh_drive_info() -> None:
        app.state.drive_info = resolve_drive_status(
            None if sa_json_path in (None, "") else sa_json_path,
            oauth_token_path=oauth_token_path,
            environ=oauth_env,
        )

    def _account_email() -> str | None:
        info = app.state.drive_info
        return info.connected_email or info.sa_email

    def _require_drive() -> None:
        if app.state.drive is None or app.state.drive_info.status != "ready":
            raise HTTPException(status_code=503, detail=app.state.drive_info.message)

    def _require_sheets() -> SheetsClient:
        if app.state.sheets is None:
            raise HTTPException(
                status_code=503,
                detail="Sheets not available — Connect Google in Settings → Drive "
                       "(must grant Spreadsheets scope)",
            )
        return app.state.sheets

    def _current_sheet_id() -> str | None:
        return resolve_sheet_id(oauth_env, drop_sheet_path)

    def _persist_sheet_id(sid: str) -> None:
        write_sheet_id_file(drop_sheet_path, sid)

    def _sync_platform_result_to_sheet(source_id: str, index: int, result: str) -> None:
        sheets_client = app.state.sheets
        sid = _current_sheet_id()
        if sheets_client is None or not sid:
            return
        loc = store._locate(source_id)
        if loc is None:
            return
        job_id, _ = loc
        try:
            update_platform_result_cell(
                sheets_client, sid,
                job_id=job_id, source_id=source_id, index=index, result=result,
            )
        except Exception as exc:
            print(f"drop ledger platform_result write failed: {exc}", flush=True)

    def _redirect_uri_for(request: Request) -> str:
        explicit = oauth_env.get(ENV_OAUTH_REDIRECT_URI)
        fallback = str(request.base_url).rstrip("/")
        base = public_request_base(request.headers, fallback)
        return resolve_redirect_uri(oauth_env, request_base=base, explicit=explicit)

    def _settings_url(request: Request, query: str) -> str:
        fallback = str(request.base_url).rstrip("/")
        origin = studio_origin_from_redirect_uri(
            _redirect_uri_for(request),
            public_request_base(request.headers, fallback),
        )
        return f"{origin}/settings/drive?{query}"

    def _run_workflow_tick(wf: Workflow) -> Workflow:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        inbox = app.state.destinations.get(wf.inbox_destination_id)
        output = app.state.destinations.get(wf.output_destination_id)
        if inbox is None or output is None:
            summary = {
                "queued": 0, "exported": 0, "skipped": 0, "failed": 0,
                "running": 0, "job_ids": [], "error": "destination missing",
            }
            return app.state.workflows.update(
                wf.id, last_sweep_at=ts, last_summary=summary, touch_sweep=True,
            ) or wf
        if app.state.drive is None or app.state.drive_info.status != "ready":
            summary = {
                "queued": 0, "exported": 0, "skipped": 0, "failed": 0,
                "running": 0, "job_ids": [],
                "error": app.state.drive_info.message,
            }
            return app.state.workflows.update(
                wf.id, last_sweep_at=ts, last_summary=summary, touch_sweep=True,
            ) or wf
        ledger = Ledger(store._ws.workflow_ledger_path(wf.id))
        with app.state.workflow_tick_lock:
            result = tick_workflow(
                wf,
                drive=app.state.drive,
                inbox_folder_id=inbox.folder_id,
                output_folder_id=output.folder_id,
                job_store=store,
                ledger=ledger,
                work_dir=store._ws.workflow_work_dir(),
                caption_store=app.state.captions,
            )
        return app.state.workflows.update(
            wf.id, last_sweep_at=ts, last_summary=result.as_dict(), touch_sweep=True,
        ) or wf

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/api/jobs", status_code=201, response_model=CreateJobResponse)
    async def create_job(files: list[UploadFile], count: int = Form(...),
                          allow_creative_escalate: bool = Form(True),
                          quality_mode: str = Form("fast")) -> CreateJobResponse:
        uploads = [(f.filename or "video.mp4", await f.read()) for f in files]
        job = store.create_job(
            uploads, count=count, allow_creative_escalate=allow_creative_escalate,
            quality_mode=quality_mode,
        )
        return CreateJobResponse(job_id=job.job_id,
                                 sources=[_source_out(s, ok_only=True, job=job, ws=store._ws)
                                          for s in job.sources])

    @app.post("/api/uploads")
    def init_upload(filename: str = Form(...), size: int = Form(...)) -> dict:
        """Start a chunked upload (RunPod HTTP proxy drops large multipart bodies)."""
        upload_id = uuid.uuid4().hex[:12]
        safe = os.path.basename(filename) or "video.mp4"
        path = store._ws.upload_blob_path(upload_id, safe)
        open(path, "wb").close()
        _UPLOAD_META[upload_id] = {"filename": safe, "size": int(size), "received": 0, "path": path}
        return {"upload_id": upload_id, "chunk_hint": 2_000_000}

    @app.put("/api/uploads/{upload_id}")
    async def put_upload_chunk(upload_id: str, request: Request, offset: int = 0) -> dict:
        meta = _UPLOAD_META.get(upload_id)
        if meta is None:
            raise HTTPException(status_code=404, detail="upload not found")
        data = await request.body()
        path = meta["path"]
        with open(path, "r+b") as f:
            f.seek(int(offset))
            f.write(data)
            received = f.tell()
            # if writing past EOF with holes, size is max
            f.seek(0, os.SEEK_END)
            received = max(received, f.tell())
        meta["received"] = max(meta["received"], received)
        return {"received": meta["received"]}

    @app.post("/api/jobs/from-uploads", status_code=201, response_model=CreateJobResponse)
    def create_job_from_uploads(
        upload_ids: str = Form(...),
        count: int = Form(...),
        allow_creative_escalate: bool = Form(True),
        quality_mode: str = Form("fast"),
    ) -> CreateJobResponse:
        ids = [u.strip() for u in upload_ids.split(",") if u.strip()]
        if not ids:
            raise HTTPException(status_code=400, detail="upload_ids required")
        paths: list[tuple[str, str]] = []
        for uid in ids:
            meta = _UPLOAD_META.get(uid)
            if meta is None:
                raise HTTPException(status_code=404, detail=f"upload not found: {uid}")
            if meta["received"] <= 0 or not os.path.exists(meta["path"]):
                raise HTTPException(status_code=400, detail=f"upload incomplete: {uid}")
            paths.append((meta["filename"], meta["path"]))
        job = store.create_job_from_paths(
            paths, count=count, allow_creative_escalate=allow_creative_escalate,
            quality_mode=quality_mode,
        )
        for uid in ids:
            _UPLOAD_META.pop(uid, None)
        return CreateJobResponse(job_id=job.job_id,
                                 sources=[_source_out(s, ok_only=True, job=job, ws=store._ws)
                                          for s in job.sources])

    @app.post("/api/jobs/from-drive", status_code=201, response_model=CreateJobResponse)
    def create_job_from_drive(body: JobFromDriveIn) -> CreateJobResponse:
        _require_drive()
        dest = app.state.destinations.get(body.destination_id)
        if dest is None:
            raise HTTPException(status_code=404, detail="destination not found")
        file_ids = [fid.strip() for fid in body.file_ids if str(fid).strip()]
        if not file_ids:
            raise HTTPException(status_code=400, detail="file_ids required")
        children = {
            f.id: f for f in app.state.drive.list_files(dest.folder_id) if is_video_file(f)
        }
        missing = [fid for fid in file_ids if fid not in children]
        if missing:
            raise HTTPException(status_code=400, detail="file is not a video in that folder")
        stage = tempfile.mkdtemp(prefix="vm_drive_in_", dir=store._ws.root)
        paths: list[tuple[str, str]] = []
        try:
            for i, fid in enumerate(file_ids):
                f = children[fid]
                name = os.path.basename(f.name) or "clip.mp4"
                local = os.path.join(stage, f"{i}_{name}")
                app.state.drive.download(fid, local)
                paths.append((name, local))
            job = store.create_job_from_paths(
                paths, count=body.count,
                allow_creative_escalate=body.allow_creative_escalate,
                quality_mode=body.quality_mode,
            )
        finally:
            shutil.rmtree(stage, ignore_errors=True)
        return CreateJobResponse(job_id=job.job_id,
                                 sources=[_source_out(s, ok_only=True, job=job, ws=store._ws)
                                          for s in job.sources])

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
                         state=job.state,
                         sources=[_source_out(s, ok_only=True, job=job, ws=store._ws)
                                  for s in job.sources],
                         error=job.error)

    @app.post("/api/jobs/{job_id}/cancel", response_model=JobDetail)
    def cancel_job(job_id: str) -> JobDetail:
        job = store.cancel(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return JobDetail(job_id=job.job_id, count=job.count, created_utc=job.created_utc,
                         state=job.state,
                         sources=[_source_out(s, ok_only=True, job=job, ws=store._ws)
                                  for s in job.sources],
                         error=job.error)

    @app.get("/api/jobs/{job_id}/events-snapshot", response_model=JobEventsSnapshot)
    def job_events_snapshot(job_id: str) -> JobEventsSnapshot:
        """Non-streaming event log for proxies that buffer SSE (e.g. RunPod HTTP)."""
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return JobEventsSnapshot(
            job_id=job.job_id,
            state=job.state,
            events=[event_to_dict(e) for e in job.events],
        )

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
                if job.state in ("done", "cancelled") and sent >= len(job.events):
                    yield {"data": json.dumps({"state": "job-done"})}
                    return
                await asyncio.sleep(0.1)

        return EventSourceResponse(gen())

    @app.get("/api/gallery", response_model=list[SourceOut])
    def gallery() -> list[SourceOut]:
        out = []
        for job in store.list():
            for s in job.sources:
                out.append(_source_out(s, ok_only=True, job=job, ws=store._ws))
        out.sort(key=lambda s: s.created_utc or "", reverse=True)
        return out

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
        loc = store._locate(source_id)
        job = store.get(loc[0]) if loc else None
        return _source_out(source, ok_only=True, job=job, ws=store._ws)

    @app.post("/api/sources/{source_id}/retry-copy", response_model=SourceOut)
    def retry_copy(source_id: str) -> SourceOut:
        source = store.retry_copy(source_id)
        if source is None:
            raise HTTPException(status_code=404, detail="source not found")
        loc = store._locate(source_id)
        job = store.get(loc[0]) if loc else None
        return _source_out(source, ok_only=True, job=job, ws=store._ws)

    @app.post("/api/variants/{source_id}/{index}/platform-result", response_model=VariantOut)
    def set_platform_result(source_id: str, index: int, body: PlatformResultIn) -> VariantOut:
        variant = store.set_platform_result(source_id, index, body.result)
        if variant is None:
            raise HTTPException(status_code=404, detail="variant not found")
        _sync_platform_result_to_sheet(source_id, index, body.result)
        loc = store._locate(source_id)
        file_ready = True
        if loc is not None:
            file_ready = variant_on_disk(store._ws, loc[0], source_id, variant.filename)
        return _variant_out(source_id, variant, file_ready=file_ready)

    @app.get("/api/drop-ledger/status", response_model=DropLedgerStatusOut)
    def drop_ledger_status() -> DropLedgerStatusOut:
        sid = _current_sheet_id()
        if sid:
            return DropLedgerStatusOut(
                configured=True, spreadsheet_id=sid,
                spreadsheet_url=spreadsheet_url(sid),
                message="Drop Ledger configured",
            )
        if app.state.sheets is None:
            return DropLedgerStatusOut(
                configured=False,
                message="Connect Google (Settings → Drive), then POST /api/drop-ledger/ensure",
            )
        return DropLedgerStatusOut(
            configured=False,
            message="No sheet yet — POST /api/drop-ledger/ensure to create VaryForge Drop Ledger",
        )

    @app.post("/api/drop-ledger/ensure", response_model=DropLedgerEnsureOut)
    def drop_ledger_ensure() -> DropLedgerEnsureOut:
        sheets_client = _require_sheets()
        existing = _current_sheet_id()
        created = existing is None
        sid = ensure_ledger(sheets_client, existing)
        _persist_sheet_id(sid)
        return DropLedgerEnsureOut(
            spreadsheet_id=sid, spreadsheet_url=spreadsheet_url(sid), created=created,
        )

    @app.post("/api/drop-ledger/sync", response_model=DropLedgerSyncOut)
    def drop_ledger_sync(body: DropLedgerSyncIn | None = None) -> DropLedgerSyncOut:
        sheets_client = _require_sheets()
        body = body or DropLedgerSyncIn()
        sid = _current_sheet_id()
        if body.ensure or not sid:
            sid = ensure_ledger(sheets_client, sid)
            _persist_sheet_id(sid)
        assert sid is not None
        job_ids = body.job_ids or list_job_ids_on_disk(store._ws.root)
        rows: list = []
        for jid in job_ids:
            rows.extend(load_manifest_rows(store._ws.root, jid))
        stats = sync_rows(sheets_client, sid, rows)
        return DropLedgerSyncOut(
            spreadsheet_id=sid,
            spreadsheet_url=spreadsheet_url(sid),
            job_ids=list(job_ids),
            rows=len(rows),
            inserted=stats["inserted"],
            updated=stats["updated"],
            unchanged=stats["unchanged"],
        )

    @app.get("/api/sources/{source_id}/zip")
    def source_zip(source_id: str):
        path = store.zip_ok_variants(source_id)
        if path is None:
            raise HTTPException(status_code=404, detail="no ok variants for source")
        return FileResponse(path, media_type="application/zip",
                            filename=f"{source_id}_variants.zip")

    @app.get("/api/drive/status", response_model=DriveStatusOut)
    def drive_status() -> DriveStatusOut:
        _refresh_drive_info()
        return _drive_status_out(app.state.drive_info)

    @app.get("/api/drive/oauth/start")
    def drive_oauth_start(request: Request):
        if not oauth_env.get(ENV_OAUTH_CLIENT_ID) or not oauth_env.get(ENV_OAUTH_CLIENT_SECRET):
            raise HTTPException(
                status_code=503,
                detail="OAuth not configured — set VARIANT_DRIVE_OAUTH_CLIENT_ID and "
                       "VARIANT_DRIVE_OAUTH_CLIENT_SECRET",
            )
        state = new_oauth_state()
        pending_store.add(state)
        redirect_uri = _redirect_uri_for(request)
        url = build_authorization_url(
            client_id=oauth_env[ENV_OAUTH_CLIENT_ID],
            redirect_uri=redirect_uri,
            state=state,
        )
        return RedirectResponse(url=url, status_code=302)

    @app.get("/api/drive/oauth/callback")
    def drive_oauth_callback(request: Request, code: str | None = None, state: str | None = None,
                             error: str | None = None):
        if error:
            return RedirectResponse(url=_settings_url(request, f"oauth=error&reason={error}"),
                                    status_code=302)
        if not code or not state:
            return RedirectResponse(url=_settings_url(request, "oauth=error&reason=missing_code"),
                                    status_code=302)
        if not pending_store.consume(state):
            return RedirectResponse(url=_settings_url(request, "oauth=error&reason=bad_state"),
                                    status_code=302)

        client_id = oauth_env.get(ENV_OAUTH_CLIENT_ID, "")
        client_secret = oauth_env.get(ENV_OAUTH_CLIENT_SECRET, "")
        redirect_uri = _redirect_uri_for(request)
        try:
            token_data = app.state.oauth_exchange(
                code=code,
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
            )
            email = app.state.oauth_fetch_email(token_data)
            if email:
                token_data = {**token_data, "email": email}
            # Persist client secrets alongside token so GoogleDrive can refresh headless
            token_data.setdefault("client_id", client_id)
            token_data.setdefault("client_secret", client_secret)
            token_store.save(token_data)
        except Exception as exc:
            print(f"oauth exchange failed: {exc}", flush=True)
            traceback.print_exc()
            return RedirectResponse(url=_settings_url(request, "oauth=error&reason=exchange_failed"),
                                    status_code=302)

        try:
            app.state.drive = _build_drive_client(oauth_token_path=oauth_token_path)
        except Exception:
            pass
        try:
            app.state.sheets = GoogleSheets(oauth_token=oauth_token_path)
        except Exception:
            pass
        _refresh_drive_info()
        return RedirectResponse(url=_settings_url(request, "oauth=connected"), status_code=302)

    @app.post("/api/drive/oauth/disconnect")
    def drive_oauth_disconnect() -> dict:
        token_store.clear()
        if app.state.drive_info.auth_mode == "oauth":
            app.state.drive = None
        _refresh_drive_info()
        # Re-attach SA client if still configured
        if app.state.drive is None and app.state.drive_info.status == "ready":
            if app.state.drive_info.auth_mode == "service_account" and sa_arg:
                app.state.drive = _build_drive_client(sa_json_path=sa_arg)
        return {"ok": True}

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
        auth_mode = app.state.drive_info.auth_mode or "service_account"
        try:
            probe_folder_writable(
                app.state.drive, folder_id,
                sa_email=_account_email(), auth_mode=auth_mode,
            )
        except DestinationError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        dest = app.state.destinations.create(
            name=body.name, folder_id=folder_id, auth_mode=auth_mode,
        )
        return _destination_out(dest)

    @app.patch("/api/drive/destinations/{dest_id}", response_model=DestinationOut)
    def update_destination(dest_id: str, body: DestinationUpdateIn) -> DestinationOut:
        _require_drive()
        existing = app.state.destinations.get(dest_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="destination not found")
        folder_id = None
        auth_mode = app.state.drive_info.auth_mode or existing.auth_mode
        if body.folder_url is not None:
            try:
                folder_id = _resolve_folder_id(body.folder_url)
            except DriveUrlError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
            if folder_id != existing.folder_id:
                try:
                    probe_folder_writable(
                        app.state.drive, folder_id,
                        sa_email=_account_email(), auth_mode=auth_mode,
                    )
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
            probe_folder_writable(
                app.state.drive, dest.folder_id,
                sa_email=_account_email(),
                auth_mode=app.state.drive_info.auth_mode or dest.auth_mode,
            )
        except DestinationError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {"ok": True}

    @app.get("/api/drive/destinations/{dest_id}/videos", response_model=DriveVideosOut)
    def list_destination_videos(dest_id: str) -> DriveVideosOut:
        _require_drive()
        dest = app.state.destinations.get(dest_id)
        if dest is None:
            raise HTTPException(status_code=404, detail="destination not found")
        videos = [
            DriveVideoOut(id=f.id, name=f.name, mime_type=f.mime_type, md5=f.md5)
            for f in app.state.drive.list_files(dest.folder_id)
            if is_video_file(f)
        ]
        return DriveVideosOut(videos=videos)

    @app.get("/api/workflows", response_model=list[WorkflowOut])
    def list_workflows() -> list[WorkflowOut]:
        return [_workflow_out(w) for w in app.state.workflows.list()]

    def _require_distinct_workflow_folders(inbox_dest_id: str, output_dest_id: str) -> None:
        inbox = app.state.destinations.get(inbox_dest_id)
        output = app.state.destinations.get(output_dest_id)
        if inbox is None:
            raise HTTPException(status_code=400, detail="unknown inbox destination")
        if output is None:
            raise HTTPException(status_code=400, detail="unknown output destination")
        if inbox.id == output.id or inbox.folder_id == output.folder_id:
            raise HTTPException(
                status_code=400, detail="inbox and output folders must be different",
            )

    @app.post("/api/workflows", status_code=201, response_model=WorkflowOut)
    def create_workflow(body: WorkflowCreateIn) -> WorkflowOut:
        _require_distinct_workflow_folders(body.inbox_destination_id, body.output_destination_id)
        try:
            wf = app.state.workflows.create(
                name=body.name,
                inbox_destination_id=body.inbox_destination_id,
                output_destination_id=body.output_destination_id,
                count=body.count,
                quality_mode=body.quality_mode,
                allow_creative_escalate=body.allow_creative_escalate,
                enabled=body.enabled,
                poll_seconds=body.poll_seconds,
                auto_caption=body.auto_caption,
                caption_bank_id=body.caption_bank_id or "",
            )
        except WorkflowError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return _workflow_out(wf)

    @app.patch("/api/workflows/{workflow_id}", response_model=WorkflowOut)
    def update_workflow(workflow_id: str, body: WorkflowUpdateIn) -> WorkflowOut:
        existing = app.state.workflows.get(workflow_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        inbox_id = existing.inbox_destination_id if body.inbox_destination_id is None else body.inbox_destination_id
        output_id = existing.output_destination_id if body.output_destination_id is None else body.output_destination_id
        _require_distinct_workflow_folders(inbox_id, output_id)
        try:
            updated = app.state.workflows.update(
                workflow_id,
                name=body.name,
                inbox_destination_id=body.inbox_destination_id,
                output_destination_id=body.output_destination_id,
                count=body.count,
                quality_mode=body.quality_mode,
                allow_creative_escalate=body.allow_creative_escalate,
                enabled=body.enabled,
                poll_seconds=body.poll_seconds,
                auto_caption=body.auto_caption,
                caption_bank_id=body.caption_bank_id,
            )
        except WorkflowError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if updated is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        return _workflow_out(updated)

    @app.delete("/api/workflows/{workflow_id}", status_code=204)
    def delete_workflow(workflow_id: str) -> None:
        if not app.state.workflows.delete(workflow_id):
            raise HTTPException(status_code=404, detail="workflow not found")
        ledger_path = store._ws.workflow_ledger_path(workflow_id)
        try:
            os.remove(ledger_path)
        except OSError:
            pass

    @app.post("/api/workflows/{workflow_id}/run", response_model=WorkflowOut)
    def run_workflow(workflow_id: str) -> WorkflowOut:
        _require_drive()
        wf = app.state.workflows.get(workflow_id)
        if wf is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        return _workflow_out(_run_workflow_tick(wf))

    @app.get("/api/caption-banks", response_model=list[CaptionBankFolderOut])
    def list_caption_banks() -> list[CaptionBankFolderOut]:
        return [_caption_folder_out(m) for m in app.state.captions.list_banks()]

    @app.post("/api/caption-banks", status_code=201, response_model=CaptionBankFolderOut)
    def create_caption_bank(body: CaptionFolderCreateIn) -> CaptionBankFolderOut:
        try:
            return _caption_folder_out(app.state.captions.create_bank(body.name))
        except CaptionError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.patch("/api/caption-banks/{bank_id}", response_model=CaptionBankFolderOut)
    def rename_caption_bank(bank_id: str, body: CaptionFolderCreateIn) -> CaptionBankFolderOut:
        try:
            meta = app.state.captions.rename_bank(bank_id, body.name)
        except CaptionError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if meta is None:
            raise HTTPException(status_code=404, detail="caption folder not found")
        return _caption_folder_out(meta)

    @app.delete("/api/caption-banks/{bank_id}", status_code=204)
    def delete_caption_bank(bank_id: str) -> None:
        try:
            ok = app.state.captions.delete_bank(bank_id)
        except CaptionError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if not ok:
            raise HTTPException(status_code=404, detail="caption folder not found")

    @app.get("/api/captions", response_model=CaptionBankOut)
    def list_captions(bank_id: str | None = None) -> CaptionBankOut:
        return _caption_bank_payload(app.state.captions, bank_id)

    @app.get("/api/captions/preview", response_model=CaptionPreviewOut)
    def preview_captions(n: int = 1, bank_id: str | None = None) -> CaptionPreviewOut:
        return CaptionPreviewOut(captions=app.state.captions.peek(max(0, n), bank_id=bank_id))

    @app.post("/api/captions", status_code=201, response_model=CaptionOut)
    def create_caption(body: CaptionCreateIn) -> CaptionOut:
        try:
            cap = app.state.captions.add(body.text, bank_id=body.bank_id)
        except CaptionError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return CaptionOut(id=cap.id, text=cap.text)

    @app.post("/api/captions/bulk", status_code=201, response_model=CaptionBankOut)
    def bulk_captions(body: CaptionBulkIn) -> CaptionBankOut:
        try:
            app.state.captions.add_many(split_caption_bank(body.raw), bank_id=body.bank_id)
        except CaptionError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return _caption_bank_payload(app.state.captions, body.bank_id)

    @app.patch("/api/captions/{caption_id}", response_model=CaptionOut)
    def update_caption(caption_id: str, body: CaptionCreateIn) -> CaptionOut:
        try:
            cap = app.state.captions.update(caption_id, body.text)
        except CaptionError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if cap is None:
            raise HTTPException(status_code=404, detail="caption not found")
        return CaptionOut(id=cap.id, text=cap.text)

    @app.delete("/api/captions/{caption_id}", status_code=204)
    def delete_caption(caption_id: str) -> None:
        if not app.state.captions.delete(caption_id):
            raise HTTPException(status_code=404, detail="caption not found")

    @app.post("/api/captions/advance", response_model=CaptionBankOut)
    def advance_captions(body: CaptionAdvanceIn) -> CaptionBankOut:
        app.state.captions.advance(body.n, bank_id=body.bank_id)
        return _caption_bank_payload(app.state.captions, body.bank_id)

    @app.post("/api/drive/exports", status_code=201, response_model=ExportJobOut)
    def create_export(body: ExportCreateIn) -> ExportJobOut:
        _require_drive()
        dest = app.state.destinations.get(body.destination_id)
        if dest is None:
            raise HTTPException(status_code=404, detail="destination not found")
        refs = [
            VariantRef(source_id=v.source_id, index=v.index, caption=v.caption)
            for v in body.variants
        ]
        try:
            files = build_export_files(store, refs)
        except ExportError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if body.consume_bank:
            app.state.captions.advance(len(files), bank_id=body.caption_bank_id)
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

    if enable_workflow_poller:
        stop = threading.Event()
        app.state.workflow_poller_stop = stop

        def _workflow_poll_delay() -> float:
            enabled = [w.poll_seconds for w in app.state.workflows.list() if w.enabled]
            return float(min(enabled)) if enabled else 30.0

        def _poll_loop() -> None:
            while not stop.wait(timeout=_workflow_poll_delay()):
                try:
                    for wf in app.state.workflows.list():
                        if wf.enabled:
                            _run_workflow_tick(wf)
                except Exception as exc:  # noqa: BLE001 — poller must not die on one sweep
                    print(f"workflow poller: {type(exc).__name__}: {exc}", flush=True)

        threading.Thread(target=_poll_loop, name="workflow-poller", daemon=True).start()

    return app
