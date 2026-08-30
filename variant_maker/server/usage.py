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
_MONTH = timedelta(days=30)
_lock = threading.Lock()


@dataclass(frozen=True)
class UsageWindow:
    sources: int = 0
    copies: int = 0
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
    """Count sources that actually delivered copies — failed packs do not burn a trial."""
    srcs = list(getattr(job, "sources", None) or [])
    copies = sum(int(getattr(s, "delivered", 0) or 0) for s in srcs)
    sources = sum(1 for s in srcs if int(getattr(s, "delivered", 0) or 0) > 0)
    return sources, copies


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


def record_job(ws: Workspace, job: Any) -> bool:
    """Append one finished job. Returns False if skipped (cancel / duplicate)."""
    if getattr(job, "state", None) != "done":
        return False
    sources, copies = _counts_for(job)
    if copies <= 0:
        return False
    path = usage_path(ws)
    with _lock:
        if job.job_id in _existing_ids(path):
            return False
        utc = str(getattr(job, "created_utc", None) or "").strip()
        if not utc:
            utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        row = {
            "utc": utc,
            "job_id": job.job_id,
            "sources": int(sources),
            "copies": int(copies),
            "packs": 1,
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    return True


def backfill_jobs(ws: Workspace, jobs: list[Any]) -> int:
    """Write any finished jobs that are not yet in the ledger. Returns rows added."""
    added = 0
    for job in jobs:
        if record_job(ws, job):
            added += 1
    return added


def _sum_since(path: str, start: datetime | None) -> UsageWindow:
    if not os.path.isfile(path):
        return UsageWindow()
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return UsageWindow()
    sources = copies = packs = 0
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
        if ts is None:
            continue
        if start is not None and ts < start:
            continue
        sources += int(row.get("sources") or 0)
        copies += int(row.get("copies") or 0)
        packs += int(row.get("packs") or 1)
    return UsageWindow(sources=sources, copies=copies, packs=packs)


def usage_windows(ws: Workspace, *, now: datetime | None = None) -> dict[str, UsageWindow]:
    """week = last 7 days, month = last 30 days, all = lifetime (trial cap)."""
    path = usage_path(ws)
    when = now or datetime.now(UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    when = when.astimezone(UTC)
    return {
        "week": _sum_since(path, when - _WEEK),
        "month": _sum_since(path, when - _MONTH),
        "all": _sum_since(path, None),
    }
