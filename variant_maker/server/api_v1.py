"""Public Studio HTTP contract: /api/v1 adapters + cookie key management.

Bearer tokens are not a session on /api/*. Cookie UI keeps its current routes.
"""
from __future__ import annotations

import base64
import os
import re
import shutil
import tempfile
from collections.abc import Callable
from typing import Any
from urllib.parse import quote, urlparse

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from variant_maker.farm.drive import DriveClient, is_video_file
from variant_maker.server.drive_oauth import public_request_base
from variant_maker.server.api_keys import (
    DEFAULT_TTL_DAYS,
    ApiKeyStore,
    ApiKeyStoreError,
    ApiPrincipal,
    append_audit,
    normalize_scopes,
    public_key_dict,
)
from variant_maker.server.api_v1_limits import (
    MAX_ACTIVE_API_EXPORTS,
    MAX_ACTIVE_API_PACKS,
    IdempotencyStore,
    LimitDecision,
    SlidingWindow,
    auth_fail_blocked,
    rate_for_auth_fail,
    rate_for_export,
    rate_for_pack,
    rate_for_read,
)
from variant_maker.server.auth_app import tenant_cv
from variant_maker.server.drive_exports import (
    ExportError,
    ExportJob,
    VariantRef,
    build_export_files,
)
from variant_maker.server.jobs import Job, job_is_in_flight

PACK_COUNTS = frozenset({8, 20})
FORBIDDEN_PUBLIC = re.compile(
    r"uniqueness|vmaf|ssim|mae|sha256|gate.?24|look_status",
    re.IGNORECASE,
)
NO_STORE = {"Cache-Control": "no-store"}


class PackCreateIn(BaseModel):
    input_destination_id: str
    drive_file_id: str
    count: int


class PackCopyOut(BaseModel):
    index: int
    filename: str
    ready: bool


class PackSourceOut(BaseModel):
    source_id: str
    filename: str
    requested: int
    ready: int
    shortfall: int
    copies: list[PackCopyOut] = []


class PackAcceptedOut(BaseModel):
    pack_id: str
    state: str
    status_url: str


class PackOut(BaseModel):
    pack_id: str
    state: str
    created_utc: str
    requested: int
    ready: int
    shortfall: int
    sources: list[PackSourceOut] = []
    error: str | None = None
    review_url: str = "/gallery"
    status_url: str = ""


class GalleryItemOut(BaseModel):
    pack_id: str | None = None
    source_id: str
    filename: str
    created_utc: str | None = None
    requested: int
    ready: int
    shortfall: int
    copies: list[PackCopyOut] = []


class GalleryPageOut(BaseModel):
    items: list[GalleryItemOut] = []
    next_cursor: str | None = None


class ExportVariantIn(BaseModel):
    source_id: str
    index: int
    caption: str | None = None


class ExportCreateIn(BaseModel):
    destination_id: str
    variants: list[ExportVariantIn]


class ExportFileOut(BaseModel):
    source_id: str
    index: int
    filename: str
    status: str
    drive_file_id: str | None = None


class ExportAcceptedOut(BaseModel):
    export_id: str
    state: str
    status_url: str
    folder_url: str | None = None


class ExportOut(BaseModel):
    export_id: str
    state: str
    destination_id: str
    folder_id: str
    folder_url: str | None = None
    created_utc: str
    completed: int = 0
    failed: int = 0
    files: list[ExportFileOut] = []
    status_url: str = ""


class ApiKeyCreateIn(BaseModel):
    label: str
    scopes: list[str] = Field(default_factory=list)
    preset: str | None = None
    expires_days: int = DEFAULT_TTL_DAYS


class ApiKeyOut(BaseModel):
    key_id: str
    label: str
    prefix: str
    scopes: list[str]
    created_utc: str
    expires_utc: str | None = None
    last_used_utc: str | None = None
    revoked_utc: str | None = None


class ApiKeyCreatedOut(ApiKeyOut):
    token: str


class DestinationIdOut(BaseModel):
    id: str
    name: str


class FoldersOut(BaseModel):
    folders: list[DestinationIdOut] = []


class ClipsOut(BaseModel):
    clips: list[DestinationIdOut] = []


class ApiKeysPageOut(BaseModel):
    workspace_id: str
    workspace_name: str | None = None
    keys: list[ApiKeyOut] = []
    destinations: list[DestinationIdOut] = []


def no_store(payload: dict, *, status_code: int = 200) -> JSONResponse:
    return JSONResponse(payload, status_code=status_code, headers=NO_STORE)


def public_pack_state(state: str | None) -> str:
    raw = str(state or "")
    if raw in ("done", "completed"):
        return "done"
    if raw == "cancelled":
        return "cancelled"
    return "running"


def public_error(raw: str | None) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if "/" in text or "\\" in text or FORBIDDEN_PUBLIC.search(text):
        return "Pack failed. Open Gallery to review."
    if len(text) > 240:
        return text[:240]
    return text


def drive_folder_url(folder_id: str | None) -> str | None:
    fid = str(folder_id or "").strip()
    if not fid:
        return None
    return f"https://drive.google.com/drive/folders/{quote(fid, safe='')}"


def _encode_cursor(created_utc: str, source_id: str) -> str:
    raw = f"{created_utc}\t{source_id}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[str, str] | None:
    raw = (cursor or "").strip()
    if not raw:
        return None
    padded = raw + "=" * ((4 - len(raw) % 4) % 4)
    try:
        text = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        created, source_id = text.split("\t", 1)
    except (ValueError, UnicodeDecodeError):
        return None
    return created, source_id


def pack_source_out(job: Job, source) -> PackSourceOut:
    copies = [
        PackCopyOut(index=int(v.index), filename=str(v.filename), ready=True)
        for v in (source.variants or [])
        if getattr(v, "status", None) == "ok"
    ]
    ready = len(copies)
    requested = int(getattr(source, "requested", 0) or 0)
    shortfall = max(0, requested - ready)
    return PackSourceOut(
        source_id=source.source_id,
        filename=source.filename,
        requested=int(getattr(source, "requested", 0) or 0),
        ready=ready,
        shortfall=shortfall,
        copies=copies,
    )


def pack_out(job: Job) -> PackOut:
    sources = [pack_source_out(job, s) for s in job.sources]
    ready = sum(s.ready for s in sources)
    requested = int(job.count or 0) * max(1, len(job.sources)) if job.sources else int(job.count or 0)
    if job.sources:
        requested = sum(s.requested for s in sources)
    shortfall = max(0, requested - ready)
    pack_id = job.job_id
    return PackOut(
        pack_id=pack_id,
        state=public_pack_state(job.state),
        created_utc=job.created_utc,
        requested=requested,
        ready=ready,
        shortfall=shortfall,
        sources=sources,
        error=public_error(job.error),
        review_url="/gallery",
        status_url=f"/api/v1/packs/{pack_id}",
    )


def gallery_item(job: Job, source) -> GalleryItemOut:
    copies = [
        PackCopyOut(index=int(v.index), filename=str(v.filename), ready=True)
        for v in (source.variants or [])
        if getattr(v, "status", None) == "ok"
    ]
    ready = len(copies)
    requested = int(getattr(source, "requested", 0) or 0)
    return GalleryItemOut(
        pack_id=job.job_id,
        source_id=source.source_id,
        filename=source.filename,
        created_utc=job.created_utc,
        requested=requested,
        ready=ready,
        shortfall=max(0, requested - ready),
        copies=copies,
    )


def export_out(job: ExportJob) -> ExportOut:
    files = [
        ExportFileOut(
            source_id=f.source_id,
            index=f.index,
            filename=f.filename,
            status=f.status,
            drive_file_id=f.drive_file_id,
        )
        for f in job.files
    ]
    return ExportOut(
        export_id=job.export_id,
        state=job.state,
        destination_id=job.destination_id,
        folder_id=job.folder_id,
        folder_url=drive_folder_url(job.folder_id),
        created_utc=job.created_utc,
        completed=sum(1 for f in job.files if f.status == "succeeded"),
        failed=sum(1 for f in job.files if f.status == "failed"),
        files=files,
        status_url=f"/api/v1/drive/exports/{job.export_id}",
    )


def bearer_token(header: str | None) -> str | None:
    raw = (header or "").strip()
    if not raw:
        return None
    kind, _, rest = raw.partition(" ")
    if kind.lower() != "bearer" or not rest.strip():
        return None
    return rest.strip()


def _peer_ip(request: Request) -> str:
    peer = request.client.host if request.client is not None else "unknown"
    return peer or "unknown"


def authorize_bearer(
    request: Request,
    *,
    auth_on: bool,
    keys: ApiKeyStore | None,
    tenants,
    hub,
    windows: SlidingWindow,
    audit_path: str | None,
) -> JSONResponse | None:
    """Bind /api/v1 bearer, or reject Authorization on any other /api path."""
    path = request.url.path
    header = request.headers.get("authorization")
    token = bearer_token(header)
    is_v1 = path == "/api/v1" or path.startswith("/api/v1/")
    if token is None:
        if is_v1 and path != "/api/v1/openapi.json":
            return no_store({"detail": "API key required"}, status_code=401)
        return None
    if not is_v1:
        return no_store({"detail": "API key cannot call this route"}, status_code=401)
    if path == "/api/v1/openapi.json":
        return None
    ip = _peer_ip(request)
    blocked = auth_fail_blocked(windows, ip)
    if not blocked.allowed:
        return JSONResponse(
            {"detail": "too many attempts"},
            status_code=429,
            headers={**NO_STORE, "Retry-After": str(blocked.retry_after)},
        )
    if not auth_on or keys is None or tenants is None or hub is None:
        return no_store({"detail": "API key required"}, status_code=401)
    try:
        rec = keys.authenticate(token, tenants=tenants)
    except ApiKeyStoreError:
        return no_store({"detail": "API key required"}, status_code=503)
    if rec is None:
        rate_for_auth_fail(windows, ip)
        if audit_path:
            append_audit(audit_path, {"op": "auth", "result": "deny", "ip": ip})
        return no_store({"detail": "invalid API key"}, status_code=401)
    try:
        keys.touch(rec.key_id)
    except ApiKeyStoreError:
        return no_store({"detail": "API key required"}, status_code=503)
    principal = ApiPrincipal(
        key_id=rec.key_id,
        workspace_id=rec.workspace_id,
        issuer_email=rec.issuer_email,
        scopes=frozenset(rec.scopes),
        label=rec.label,
    )
    request.state.api_principal = principal
    request.state.user = None
    request.state.viewing_workspace_id = rec.workspace_id
    tenant_cv.set(hub.bundle(rec.workspace_id))
    return None


def require_principal(request: Request) -> ApiPrincipal:
    principal = getattr(request.state, "api_principal", None)
    if not isinstance(principal, ApiPrincipal):
        raise HTTPException(status_code=401, detail="API key required")
    return principal


def require_scope(request: Request, scope: str) -> ApiPrincipal:
    principal = require_principal(request)
    if scope not in principal.scopes:
        raise HTTPException(status_code=403, detail="missing scope")
    return principal


def _idempotency_key(request: Request) -> str:
    raw = (request.headers.get("idempotency-key") or "").strip()
    if not raw or len(raw) > 256:
        raise HTTPException(status_code=400, detail="Idempotency-Key required")
    return raw


def _limit_or_429(decision: LimitDecision) -> None:
    if decision.allowed:
        return
    raise HTTPException(
        status_code=429,
        detail="rate limit",
        headers={"Retry-After": str(decision.retry_after), **NO_STORE},
    )


def same_origin_ok(request: Request) -> bool:
    """Cookie key create/revoke must come from this Studio host.

    Next.js rewrites to FastAPI over HTTP on 127.0.0.1, so ``request.base_url``
    is not the browser Origin (HTTPS public host). Compare hosts, not the
    internal bind URL.
    """
    origin = (request.headers.get("origin") or "").strip().rstrip("/")
    if not origin:
        return True
    fallback = str(request.base_url).rstrip("/")
    public = public_request_base(request.headers, fallback).rstrip("/")
    origin_host = (urlparse(origin).netloc or "").lower()
    public_host = (urlparse(public).netloc or "").lower()
    if origin == public or (origin_host and public_host and origin_host == public_host):
        return True
    raw_host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("X-Forwarded-Host")
        or request.headers.get("host")
        or request.headers.get("Host")
        or ""
    ).split(",")[0].strip().lower()
    return bool(origin_host and raw_host and origin_host == raw_host)


def create_fast_pack_from_drive(
    *,
    store,
    destinations,
    drive: DriveClient,
    off_volume: bool,
    input_destination_id: str,
    drive_file_id: str,
    count: int,
    actor_email: str | None,
    api_key_id: str,
) -> Job:
    dest = destinations.get(input_destination_id)
    if dest is None:
        raise HTTPException(status_code=404, detail="destination not found")
    fid = str(drive_file_id or "").strip()
    if not fid:
        raise HTTPException(status_code=400, detail="drive_file_id required")
    children = {f.id: f for f in drive.list_files(dest.folder_id) if is_video_file(f)}
    if fid not in children:
        raise HTTPException(status_code=400, detail="file is not a video in that folder")
    name = os.path.basename(children[fid].name) or "clip.mp4"
    if off_volume:
        job = store.create_job_from_drive_ids(
            [(name, fid)],
            count=count,
            allow_creative_escalate=True,
            quality_mode="fast",
            generate_captions=False,
            prep_mode="none",
            actor_email=actor_email,
        )
    else:
        stage = tempfile.mkdtemp(prefix="vm_api_drive_")
        try:
            local = os.path.join(stage, name)
            drive.download(fid, local)
            job = store.create_job_from_paths(
                [(name, local)],
                count=count,
                allow_creative_escalate=True,
                quality_mode="fast",
                generate_captions=False,
                prep_mode="none",
                actor_email=actor_email,
            )
        finally:
            shutil.rmtree(stage, ignore_errors=True)
    tel = job.telemetry if isinstance(job.telemetry, dict) else {}
    tel["via"] = "api_v1"
    tel["api_key_id"] = api_key_id
    job.telemetry = tel
    return job


def _active_api_packs(store) -> int:
    n = 0
    for job in store.list():
        if not job_is_in_flight(job.state):
            continue
        if (job.telemetry or {}).get("via") == "api_v1":
            n += 1
    return n


def _active_api_exports(exports) -> int:
    n = 0
    for job in exports.list():
        if job.state not in ("pending", "running"):
            continue
        if getattr(job, "created_via", None) == "api_v1":
            n += 1
    return n


def _v1_openapi() -> dict:
    docs = FastAPI(title="varimo Studio API", version="v1")

    @docs.post("/packs", response_model=PackAcceptedOut, status_code=201)
    def _create(body: PackCreateIn) -> PackAcceptedOut:  # pragma: no cover
        return PackAcceptedOut(pack_id="x", state="running", status_url="/api/v1/packs/x")

    @docs.get("/packs/{pack_id}", response_model=PackOut)
    def _get(pack_id: str) -> PackOut:  # pragma: no cover
        return PackOut(pack_id=pack_id, state="running", created_utc="", requested=0, ready=0, shortfall=0)

    @docs.get("/gallery", response_model=GalleryPageOut)
    def _gallery() -> GalleryPageOut:  # pragma: no cover
        return GalleryPageOut()

    @docs.get("/drive/destinations", response_model=FoldersOut)
    def _folders() -> FoldersOut:  # pragma: no cover
        return FoldersOut()

    @docs.get("/drive/destinations/{dest_id}/videos", response_model=ClipsOut)
    def _clips(dest_id: str) -> ClipsOut:  # pragma: no cover
        return ClipsOut()

    @docs.post("/drive/exports", response_model=ExportAcceptedOut, status_code=201)
    def _export(body: ExportCreateIn) -> ExportAcceptedOut:  # pragma: no cover
        return ExportAcceptedOut(export_id="e", state="pending", status_url="/api/v1/drive/exports/e")

    @docs.get("/drive/exports/{export_id}", response_model=ExportOut)
    def _export_get(export_id: str) -> ExportOut:  # pragma: no cover
        return ExportOut(
            export_id=export_id, state="pending", destination_id="", folder_id="", created_utc="",
        )

    spec = docs.openapi()
    spec["info"]["description"] = (
        "Workspace API for Fast packs from a Drive clip, Gallery metadata, and Drive export. "
        "List folders and clips by name with the key — operators do not fill destination or file ids. "
        "Review copies in Studio. No media download, no Instagram, no fingerprint internals."
    )
    return spec


def register_api_v1(
    app: FastAPI,
    *,
    auth_on: bool,
    keys: ApiKeyStore | None,
    idem: IdempotencyStore | None,
    windows: SlidingWindow,
    audit_path: str | None,
    require_drive: Callable[[], None],
    get_drive: Callable[[], DriveClient | None],
    off_volume: Callable[[], bool],
    export_runner: Callable[[], Any],
    require_home_owner: Callable[[Request], Any],
    tenants,
) -> None:
    store = app.state.store

    def _audit(op: str, request: Request, *, result: str, resource: str | None = None) -> None:
        if not audit_path:
            return
        principal = getattr(request.state, "api_principal", None)
        append_audit(audit_path, {
            "op": op,
            "result": result,
            "resource": resource,
            "key_id": getattr(principal, "key_id", None),
            "workspace_id": getattr(principal, "workspace_id", None),
        })

    @app.get("/api/v1/openapi.json")
    def v1_openapi() -> dict:
        return _v1_openapi()

    @app.get("/api/workspace/api-keys", response_model=ApiKeysPageOut)
    def list_api_keys(request: Request) -> ApiKeysPageOut:
        if not auth_on or keys is None or tenants is None:
            raise HTTPException(status_code=404, detail="auth is off")
        owner = require_home_owner(request)
        recs = keys.list_for_workspace(owner.workspace_id)
        ws = tenants.get_workspace(owner.workspace_id)
        dests = [
            DestinationIdOut(id=d.id, name=d.name)
            for d in app.state.destinations.list()
        ]
        return ApiKeysPageOut(
            workspace_id=owner.workspace_id,
            workspace_name=ws.name if ws else None,
            keys=[ApiKeyOut(**public_key_dict(r)) for r in recs],
            destinations=dests,
        )

    @app.post("/api/workspace/api-keys", status_code=201)
    def create_api_key(request: Request, body: ApiKeyCreateIn) -> JSONResponse:
        if not auth_on or keys is None or tenants is None:
            raise HTTPException(status_code=404, detail="auth is off")
        if not same_origin_ok(request):
            raise HTTPException(status_code=403, detail="origin mismatch")
        owner = require_home_owner(request)
        try:
            scopes = normalize_scopes(body.scopes, preset=body.preset)
            issued = keys.create(
                workspace_id=owner.workspace_id,
                issuer_email=owner.email,
                label=body.label,
                scopes=scopes,
                ttl_days=body.expires_days,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ApiKeyStoreError as exc:
            raise HTTPException(status_code=503, detail="api key store unavailable") from exc
        payload = {**public_key_dict(issued.record), "token": issued.token}
        if audit_path:
            append_audit(audit_path, {
                "op": "key.create",
                "result": "ok",
                "key_id": issued.record.key_id,
                "workspace_id": owner.workspace_id,
            })
        return no_store(payload, status_code=201)

    @app.delete("/api/workspace/api-keys/{key_id}", status_code=204)
    def delete_api_key(request: Request, key_id: str) -> Response:
        if not auth_on or keys is None:
            raise HTTPException(status_code=404, detail="auth is off")
        if not same_origin_ok(request):
            raise HTTPException(status_code=403, detail="origin mismatch")
        owner = require_home_owner(request)
        rec = keys.revoke(key_id, workspace_id=owner.workspace_id)
        if rec is None:
            raise HTTPException(status_code=404, detail="key not found")
        return Response(status_code=204, headers=NO_STORE)

    @app.get("/api/v1/drive/destinations", response_model=FoldersOut)
    def v1_list_folders(request: Request) -> JSONResponse:
        principal = require_scope(request, "jobs:read")
        _limit_or_429(rate_for_read(windows, key_id=principal.key_id, workspace_id=principal.workspace_id))
        folders = [
            DestinationIdOut(id=d.id, name=d.name).model_dump()
            for d in app.state.destinations.list()
        ]
        return no_store({"folders": folders})

    @app.get("/api/v1/drive/destinations/{dest_id}/videos", response_model=ClipsOut)
    def v1_list_clips(request: Request, dest_id: str) -> JSONResponse:
        principal = require_scope(request, "jobs:read")
        _limit_or_429(rate_for_read(windows, key_id=principal.key_id, workspace_id=principal.workspace_id))
        dest = app.state.destinations.get(dest_id)
        if dest is None:
            raise HTTPException(status_code=404, detail="destination not found")
        require_drive()
        drive = get_drive()
        if drive is None:
            raise HTTPException(status_code=503, detail="Drive is not connected")
        clips = [
            DestinationIdOut(id=f.id, name=f.name).model_dump()
            for f in drive.list_files(dest.folder_id)
            if is_video_file(f)
        ]
        return no_store({"clips": clips})

    @app.post("/api/v1/packs", status_code=201)
    def create_pack(request: Request, body: PackCreateIn) -> JSONResponse:
        principal = require_scope(request, "jobs:create")
        _limit_or_429(rate_for_pack(windows, key_id=principal.key_id, workspace_id=principal.workspace_id))
        if body.count not in PACK_COUNTS:
            raise HTTPException(status_code=400, detail="count must be 8 or 20")
        if idem is None:
            raise HTTPException(status_code=503, detail="API key required")
        idem_key = f"{principal.workspace_id}:POST:/api/v1/packs:{_idempotency_key(request)}"
        existing = idem.begin(idem_key)
        if existing is not None:
            if existing.get("state") == "done" and isinstance(existing.get("body"), dict):
                return no_store(existing["body"], status_code=int(existing.get("status_code") or 201))
            raise HTTPException(status_code=409, detail="request in progress")
        if _active_api_packs(store) >= MAX_ACTIVE_API_PACKS:
            idem.drop(idem_key)
            raise HTTPException(status_code=429, detail="too many in-flight packs")
        require_drive()
        drive = get_drive()
        if drive is None:
            idem.drop(idem_key)
            raise HTTPException(status_code=503, detail="Drive is not connected")
        try:
            job = create_fast_pack_from_drive(
                store=store,
                destinations=app.state.destinations,
                drive=drive,
                off_volume=off_volume(),
                input_destination_id=body.input_destination_id,
                drive_file_id=body.drive_file_id,
                count=body.count,
                actor_email=principal.issuer_email,
                api_key_id=principal.key_id,
            )
        except HTTPException:
            idem.drop(idem_key)
            raise
        payload = PackAcceptedOut(
            pack_id=job.job_id,
            state=public_pack_state(job.state),
            status_url=f"/api/v1/packs/{job.job_id}",
        ).model_dump()
        idem.finish(idem_key, status_code=201, body=payload)
        _audit("packs.create", request, result="ok", resource=job.job_id)
        return no_store(payload, status_code=201)

    @app.get("/api/v1/packs/{pack_id}", response_model=PackOut)
    def get_pack(request: Request, pack_id: str) -> JSONResponse:
        principal = require_scope(request, "jobs:read")
        _limit_or_429(rate_for_read(windows, key_id=principal.key_id, workspace_id=principal.workspace_id))
        job = store.get(pack_id)
        if job is None:
            raise HTTPException(status_code=404, detail="pack not found")
        return no_store(pack_out(job).model_dump())

    @app.get("/api/v1/gallery", response_model=GalleryPageOut)
    def v1_gallery(
        request: Request, pack_id: str | None = None, limit: int = 25, cursor: str | None = None,
    ) -> JSONResponse:
        principal = require_scope(request, "gallery:read")
        _limit_or_429(rate_for_read(windows, key_id=principal.key_id, workspace_id=principal.workspace_id))
        size = min(100, max(1, int(limit)))
        items: list[GalleryItemOut] = []
        for job in store.list():
            if pack_id and job.job_id != pack_id:
                continue
            for source in job.sources:
                items.append(gallery_item(job, source))
        items.sort(key=lambda i: (i.created_utc or "", i.source_id), reverse=True)
        after = _decode_cursor(cursor or "")
        if after is not None:
            created, source_id = after
            items = [
                i for i in items
                if (i.created_utc or "", i.source_id) < (created, source_id)
            ]
        page = items[:size]
        next_cursor = None
        if len(items) > size and page:
            last = page[-1]
            next_cursor = _encode_cursor(last.created_utc or "", last.source_id)
        return no_store(GalleryPageOut(items=page, next_cursor=next_cursor).model_dump())

    @app.post("/api/v1/drive/exports", status_code=201)
    def create_v1_export(request: Request, body: ExportCreateIn) -> JSONResponse:
        principal = require_scope(request, "drive:export")
        _limit_or_429(rate_for_export(windows, key_id=principal.key_id, workspace_id=principal.workspace_id))
        if idem is None:
            raise HTTPException(status_code=503, detail="API key required")
        idem_key = f"{principal.workspace_id}:POST:/api/v1/drive/exports:{_idempotency_key(request)}"
        existing = idem.begin(idem_key)
        if existing is not None:
            if existing.get("state") == "done" and isinstance(existing.get("body"), dict):
                return no_store(existing["body"], status_code=int(existing.get("status_code") or 201))
            raise HTTPException(status_code=409, detail="request in progress")
        if _active_api_exports(app.state.exports) >= MAX_ACTIVE_API_EXPORTS:
            idem.drop(idem_key)
            raise HTTPException(status_code=429, detail="too many in-flight exports")
        require_drive()
        dest = app.state.destinations.get(body.destination_id)
        if dest is None:
            idem.drop(idem_key)
            raise HTTPException(status_code=404, detail="destination not found")
        refs = [
            VariantRef(source_id=v.source_id, index=v.index, caption=v.caption)
            for v in body.variants
        ]
        try:
            files = build_export_files(store, refs)
        except ExportError as exc:
            idem.drop(idem_key)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        job = app.state.exports.create(
            destination_id=dest.id, folder_id=dest.folder_id, files=files, created_via="api_v1",
        )
        export_runner().start(job)
        payload = ExportAcceptedOut(
            export_id=job.export_id,
            state=job.state,
            status_url=f"/api/v1/drive/exports/{job.export_id}",
            folder_url=drive_folder_url(job.folder_id),
        ).model_dump()
        idem.finish(idem_key, status_code=201, body=payload)
        _audit("exports.create", request, result="ok", resource=job.export_id)
        return no_store(payload, status_code=201)

    @app.get("/api/v1/drive/exports/{export_id}", response_model=ExportOut)
    def get_v1_export(request: Request, export_id: str) -> JSONResponse:
        principal = require_scope(request, "drive:export")
        _limit_or_429(rate_for_read(windows, key_id=principal.key_id, workspace_id=principal.workspace_id))
        job = app.state.exports.get(export_id)
        if job is None:
            raise HTTPException(status_code=404, detail="export not found")
        return no_store(export_out(job).model_dump())
