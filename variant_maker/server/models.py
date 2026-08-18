"""Pydantic response models — the HTTP contract the frontend consumes."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class VariantOut(BaseModel):
    index: int
    filename: str
    status: str
    quality: dict
    file_url: str
    uniqueness: float | None = None
    uniqueness_status: str | None = None
    uniqueness_metric: str | None = None
    uniqueness_target: float | None = None
    preset_used: str | None = None
    strength_final: float | None = None
    escalated: bool = False
    platform_result: str | None = None


class PlatformResultIn(BaseModel):
    result: Literal["passed", "duplicate_reject", "flagged", "unknown"]


class InFlightOut(BaseModel):
    """Live mid-variant state for proxies that buffer SSE."""
    index: int
    state: str
    attempt: int = 0
    max_attempts: int = 0


class SourceOut(BaseModel):
    source_id: str
    filename: str
    requested: int
    delivered: int
    shortfall: int
    variants: list[VariantOut] = []
    in_flight: InFlightOut | None = None
    job_state: str | None = None  # "running" | "done" | "cancelled"
    failed: int = 0               # best_effort + corrupt count (Diagnostics population)


class JobSummary(BaseModel):
    job_id: str
    count: int
    created_utc: str
    state: str
    source_count: int


class JobDetail(BaseModel):
    job_id: str
    count: int
    created_utc: str
    state: str
    sources: list[SourceOut] = []
    error: str | None = None


class JobEventsSnapshot(BaseModel):
    """JSON replay of the in-memory event log — used when SSE is buffered by a proxy."""
    job_id: str
    state: str
    events: list[dict] = []


class CreateJobResponse(BaseModel):
    job_id: str
    sources: list[SourceOut] = []


class DiagnosticsItem(BaseModel):
    source_id: str
    index: int
    filename: str
    status: str
    quality: dict


class DriveStatusOut(BaseModel):
    status: str
    sa_email: str | None = None
    message: str
    auth_mode: str | None = None
    connected_email: str | None = None
    oauth_available: bool = False


class DestinationOut(BaseModel):
    id: str
    name: str
    folder_id: str
    auth_mode: str


class DestinationCreateIn(BaseModel):
    name: str
    folder_url: str


class DestinationUpdateIn(BaseModel):
    name: str | None = None
    folder_url: str | None = None


class ExportVariantRefIn(BaseModel):
    source_id: str
    index: int


class ExportCreateIn(BaseModel):
    destination_id: str
    variants: list[ExportVariantRefIn]


class ExportFileOut(BaseModel):
    source_id: str
    index: int
    filename: str
    status: str
    error: str | None = None
    drive_file_id: str | None = None


class ExportJobOut(BaseModel):
    export_id: str
    destination_id: str
    folder_id: str
    state: str
    created_utc: str
    files: list[ExportFileOut] = []


class DropLedgerStatusOut(BaseModel):
    configured: bool
    spreadsheet_id: str | None = None
    spreadsheet_url: str | None = None
    message: str


class DropLedgerSyncIn(BaseModel):
    job_ids: list[str] | None = None  # None / empty → all jobs on disk
    ensure: bool = True


class DropLedgerSyncOut(BaseModel):
    spreadsheet_id: str
    spreadsheet_url: str
    job_ids: list[str]
    rows: int
    inserted: int
    updated: int
    unchanged: int


class DropLedgerEnsureOut(BaseModel):
    spreadsheet_id: str
    spreadsheet_url: str
    created: bool
