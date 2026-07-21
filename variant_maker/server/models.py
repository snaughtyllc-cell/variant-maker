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
    result: Literal["passed", "duplicate_reject", "unknown"]


class SourceOut(BaseModel):
    source_id: str
    filename: str
    requested: int
    delivered: int
    shortfall: int
    variants: list[VariantOut] = []


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
