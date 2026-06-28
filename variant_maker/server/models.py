"""Pydantic response models — the HTTP contract the frontend consumes."""
from __future__ import annotations

from pydantic import BaseModel


class VariantOut(BaseModel):
    index: int
    filename: str
    status: str
    quality: dict
    file_url: str


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
