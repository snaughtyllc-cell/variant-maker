"""Workspace usage ledger. Lives next to jobs/, so Gallery prune cannot erase a week."""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from .workspace import Workspace

USAGE_FILENAME = "usage.jsonl"
_WEEK = timedelta(days=7)
_lock = threading.Lock()


@dataclass(frozen=True)
class WeekRollup:
    fast_copies: int = 0
    hq_preps: int = 0
    packs: int = 0


UNATTRIBUTED_EMAIL = "unattributed"


@dataclass(frozen=True)
class UserWeek:
    email: str
    fast_copies: int = 0
    hq_preps: int = 0
    packs: int = 0


def usage_path(ws: Workspace) -> str:
    return os.path.join(ws.root, USAGE_FILENAME)


def _parse_utc(value: str | None) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _counts_for(job: Any) -> tuple[int, int]:
    delivered = sum(s.delivered for s in job.sources)
    if job.prep_mode == "hq":
        hq = sum(1 for s in job.sources if getattr(s, "prep_status", None) == "done")
        return delivered, hq
    if job.quality_mode == "hq":
        return 0, delivered
    return delivered, 0


def _existing_ids(path: str) -> set[str]:
    ids: set[str] = set()
    if not os.path.isfile(path):
        return ids
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict) and row.get("job_id"):
                    ids.add(str(row["job_id"]))
    except OSError:
        return ids
    return ids


def record_job(
    ws: Workspace,
    job: Any,
    *,
    now: datetime | None = None,
) -> bool:
    """Append one finished job. Returns False if skipped (cancel / duplicate)."""
    if job.state != "done":
        return False
    path = usage_path(ws)
    with _lock:
        if job.job_id in _existing_ids(path):
            return False
        when = now or datetime.now(UTC)
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        fast_copies, hq_preps = _counts_for(job)
        tel = getattr(job, "telemetry", None) or {}
        if not isinstance(tel, dict):
            tel = {}
        row = {
            "utc": when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "job_id": job.job_id,
            "fast_copies": int(fast_copies),
            "hq_preps": int(hq_preps),
            "packs": 1,
            "prep_mode": job.prep_mode,
            "quality_mode": job.quality_mode,
        }
        for key in (
            "workspace_id", "customer_email", "runpod_job_id", "runpod_endpoint_id",
            "requested", "submitted_utc", "started_utc", "completed_utc",
            "shutdown_utc", "retry_count", "regen_count", "input_bytes",
            "output_bytes", "railway_media_bytes", "delivery_destination",
            "runpod_cost_usd", "processing_charge",
            "start_class", "startup", "billed", "first_output_utc",
        ):
            if key in tel and tel[key] is not None:
                row[key] = tel[key]
        if isinstance(tel.get("source"), dict):
            row["source"] = tel["source"]
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    return True


def week_rollup(ws: Workspace, *, now: datetime | None = None) -> WeekRollup:
    path = usage_path(ws)
    if not os.path.isfile(path):
        return WeekRollup()
    when = now or datetime.now(UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    when = when.astimezone(UTC)
    start = when - _WEEK
    fast = hq = packs = 0
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return WeekRollup()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        ts = _parse_utc(str(row.get("utc") or ""))
        if ts is None or ts < start:
            continue
        fast += int(row.get("fast_copies") or 0)
        hq += int(row.get("hq_preps") or 0)
        packs += int(row.get("packs") or 1)
    return WeekRollup(fast_copies=fast, hq_preps=hq, packs=packs)


def _actor_email(row: dict[str, Any]) -> str:
    raw = str(row.get("customer_email") or "").strip().lower()
    return raw or UNATTRIBUTED_EMAIL


def user_week_rollup(ws: Workspace, *, now: datetime | None = None) -> list[UserWeek]:
    """Last-7-day Fast/HQ/packs grouped by the operator who submitted the job."""
    path = usage_path(ws)
    if not os.path.isfile(path):
        return []
    when = now or datetime.now(UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    when = when.astimezone(UTC)
    start = when - _WEEK
    grouped: dict[str, list[int]] = {}
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        ts = _parse_utc(str(row.get("utc") or ""))
        if ts is None or ts < start:
            continue
        email = _actor_email(row)
        bucket = grouped.setdefault(email, [0, 0, 0])
        bucket[0] += int(row.get("fast_copies") or 0)
        bucket[1] += int(row.get("hq_preps") or 0)
        bucket[2] += int(row.get("packs") or 1)
    rows = [
        UserWeek(email=email, fast_copies=fast, hq_preps=hq, packs=packs)
        for email, (fast, hq, packs) in grouped.items()
    ]
    rows.sort(key=lambda row: (row.email == UNATTRIBUTED_EMAIL, row.email))
    return rows
