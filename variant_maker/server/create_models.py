"""Pydantic models for Create-mode HTTP contract."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


AspectRatio = Literal["9:16", "1:1", "16:9"]


class PromptOut(BaseModel):
    positive: str
    negative: str
    notes: str = ""


class CreateStillOut(BaseModel):
    index: int
    filename: str
    handoff_filename: str
    status: str
    file_url: str
    handoff_url: str


class CreateJobSummary(BaseModel):
    job_id: str
    state: str
    brief: str
    aspect: AspectRatio
    count: int
    created_utc: str


class CreateJobDetail(CreateJobSummary):
    stills: list[CreateStillOut] = Field(default_factory=list)
    prompt: PromptOut | None = None
    error: str | None = None
    identities: list[str] = Field(default_factory=list)


class CreateJobResponse(CreateJobSummary):
    """Returned from POST /api/create/jobs (job may still be running)."""
    pass
