"""Workspace experience: solo creator vs agency.

Missing/unknown values stay **agency** so existing operator studios keep
Workflows, Drops, and the full chrome. Solo is opt-in via workspace field
or VARIANT_SOLO_EMAILS.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Literal

Experience = Literal["solo", "agency"]

SOLO_EMAILS_ENV = "VARIANT_SOLO_EMAILS"
AGENCY_EMAILS_ENV = "VARIANT_AGENCY_EMAILS"
DEFAULT_EXPERIENCE_ENV = "VARIANT_DEFAULT_EXPERIENCE"


def normalize_experience(raw: object | None) -> Experience:
    text = str(raw or "").strip().lower()
    if text == "solo":
        return "solo"
    return "agency"


def _email_set(raw: str) -> set[str]:
    return {part.strip().lower() for part in (raw or "").split(",") if part.strip()}


def resolve_experience(
    *,
    workspace_experience: object | None = None,
    email: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> Experience:
    env = os.environ if environ is None else environ
    addr = (email or "").strip().lower()
    if addr and addr in _email_set(env.get(SOLO_EMAILS_ENV, "")):
        return "solo"
    if addr and addr in _email_set(env.get(AGENCY_EMAILS_ENV, "")):
        return "agency"
    stored = str(workspace_experience or "").strip()
    if stored:
        return normalize_experience(stored)
    return normalize_experience(env.get(DEFAULT_EXPERIENCE_ENV, "agency"))
