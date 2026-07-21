"""Pydantic models for Create-mode HTTP contract."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


AspectRatio = Literal["9:16", "1:1", "16:9"]
IdentityMode = Literal["face", "lora", "both"]


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
    phase: str = "queued"
    message: str | None = None
    stills: list[CreateStillOut] = Field(default_factory=list)
    prompt: PromptOut | None = None
    error: str | None = None
    identities: list[str] = Field(default_factory=list)
    identity_mode: IdentityMode = "face"
    lora_id: str | None = None
    lora_strength: float | None = None


class CreateJobResponse(CreateJobSummary):
    """Returned from POST /api/create/jobs (job may still be running)."""
    pass


class LoraOut(BaseModel):
    id: str
    name: str
    trigger_word: str = ""
    default_strength: float = 0.8
    filename: str
    created_utc: str
    comfy_name: str = ""


class LoraTrainStatus(BaseModel):
    """Train is not in-process yet — upload a finished .safetensors instead."""

    status: Literal["unavailable"] = "unavailable"
    message: str = (
        "On-pod LoRA training is not enabled yet. "
        "Train offline (kohya / sd-scripts) and upload the .safetensors via POST /api/create/loras."
    )
    docs: str = "deploy/comfy/train_lora.md"
