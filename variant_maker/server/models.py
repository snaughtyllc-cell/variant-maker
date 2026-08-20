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
    file_ready: bool = True


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
    created_utc: str | None = None
    files_ready: int = 0          # ok variants whose mp4 is on Studio disk
    copy_status: Literal["ok", "copying", "missing"] = "ok"
    job_id: str | None = None


class JobSummary(BaseModel):
    job_id: str
    count: int
    created_utc: str
    state: str
    source_count: int


class QueueItemOut(BaseModel):
    job_id: str
    quality_mode: str
    state: str
    created_utc: str
    count: int
    source_count: int
    filenames: list[str]
    delivered: int
    requested: int
    position: int


class QueueOut(BaseModel):
    """Live generating packs on this Studio URL — filenames only, no video."""
    running: int
    fast: int = 0
    hq: int = 0
    jobs: list[QueueItemOut] = []


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
    caption: str | None = None


class ExportCreateIn(BaseModel):
    destination_id: str
    variants: list[ExportVariantRefIn]
    consume_bank: bool = False
    caption_bank_id: str | None = None


class ExportSplitDestIn(BaseModel):
    destination_id: str
    label: str | None = None
    count: int | None = None


class ExportSplitIn(BaseModel):
    job_id: str | None = None
    selected: list[ExportVariantRefIn] | None = None
    variants: list[ExportVariantRefIn] | None = None
    destinations: list[ExportSplitDestIn] | None = None
    destination_ids: list[str] | None = None
    consume_bank: bool = False
    caption_bank_id: str | None = None


class SplitExportJobOut(BaseModel):
    id: str
    dest: str
    files: list[str]
    count: int
    label: str | None = None


class SplitExportOut(BaseModel):
    ok: bool = True
    jobs: list[SplitExportJobOut] = []
    split: list[list[int]] = []


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


class DriveVideoOut(BaseModel):
    id: str
    name: str
    mime_type: str
    md5: str | None = None


class DriveVideosOut(BaseModel):
    videos: list[DriveVideoOut] = []


class JobFromDriveIn(BaseModel):
    destination_id: str
    file_ids: list[str]
    count: int
    quality_mode: str = "fast"
    allow_creative_escalate: bool = True


class WorkflowSummaryOut(BaseModel):
    queued: int = 0
    exported: int = 0
    skipped: int = 0
    failed: int = 0
    running: int = 0
    job_ids: list[str] = []
    error: str | None = None


class WorkflowOut(BaseModel):
    id: str
    name: str
    inbox_destination_id: str
    output_destination_id: str
    count: int
    quality_mode: str
    allow_creative_escalate: bool
    enabled: bool
    poll_seconds: int
    last_sweep_at: str | None = None
    last_summary: WorkflowSummaryOut | None = None
    auto_caption: bool = False
    caption_bank_id: str | None = None


class WorkflowCreateIn(BaseModel):
    name: str
    inbox_destination_id: str
    output_destination_id: str
    count: int = 20
    quality_mode: str = "fast"
    allow_creative_escalate: bool = True
    enabled: bool = False
    poll_seconds: int = 120
    auto_caption: bool = False
    caption_bank_id: str | None = None


class WorkflowUpdateIn(BaseModel):
    name: str | None = None
    inbox_destination_id: str | None = None
    output_destination_id: str | None = None
    count: int | None = None
    quality_mode: str | None = None
    allow_creative_escalate: bool | None = None
    enabled: bool | None = None
    poll_seconds: int | None = None
    auto_caption: bool | None = None
    caption_bank_id: str | None = None


class CaptionOut(BaseModel):
    id: str
    text: str


class CaptionBankFolderOut(BaseModel):
    id: str
    name: str
    is_default: bool = False
    count: int = 0
    remaining: int = 0
    cursor: int = 0
    low: bool = False


class CaptionBankOut(BaseModel):
    cursor: int = 0
    items: list[CaptionOut] = []
    bank_id: str = ""
    bank_name: str = ""
    count: int = 0
    remaining: int = 0
    low: bool = False
    is_default: bool = False


class CaptionCreateIn(BaseModel):
    text: str
    bank_id: str | None = None


class CaptionBulkIn(BaseModel):
    raw: str
    bank_id: str | None = None


class CaptionAdvanceIn(BaseModel):
    n: int
    bank_id: str | None = None


class CaptionFolderCreateIn(BaseModel):
    name: str


class CaptionPreviewOut(BaseModel):
    captions: list[str] = []
