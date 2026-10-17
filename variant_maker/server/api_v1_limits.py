"""In-process rate limits and JSON idempotency for /api/v1. No Redis."""
from __future__ import annotations

import datetime as _dt
import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from typing import Any

from variant_maker.server.api_keys import utc_now

READS_PER_KEY_MIN = 60
PACKS_PER_KEY_MIN = 6
EXPORTS_PER_KEY_MIN = 6
READS_PER_WORKSPACE_MIN = 180
PACKS_PER_WORKSPACE_MIN = 12
EXPORTS_PER_WORKSPACE_MIN = 12
MAX_ACTIVE_API_PACKS = 2
MAX_ACTIVE_API_EXPORTS = 2
AUTH_FAIL_MAX = 20
AUTH_FAIL_WINDOW_S = 15 * 60
IDEMPOTENCY_TTL_S = 24 * 60 * 60
WINDOW_S = 60.0


def _expired(created_utc: str, now_utc: str) -> bool:
    try:
        created = _dt.datetime.strptime(created_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.UTC)
        now = _dt.datetime.strptime(now_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.UTC)
    except ValueError:
        return False
    return (now - created).total_seconds() > IDEMPOTENCY_TTL_S


@dataclass
class LimitDecision:
    allowed: bool
    retry_after: int = 1


class SlidingWindow:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, list[float]] = {}

    def blocked(self, key: str, limit: int, *, window_s: float = WINDOW_S) -> LimitDecision:
        now = time.time()
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < window_s]
            self._hits[key] = hits
            if len(hits) >= max(1, int(limit)):
                oldest = hits[0] if hits else now
                retry = max(1, int(window_s - (now - oldest)) + 1)
                return LimitDecision(False, retry)
            return LimitDecision(True, 1)

    def hit(self, key: str, limit: int, *, window_s: float = WINDOW_S) -> LimitDecision:
        now = time.time()
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < window_s]
            if len(hits) >= max(1, int(limit)):
                oldest = hits[0] if hits else now
                retry = max(1, int(window_s - (now - oldest)) + 1)
                self._hits[key] = hits
                return LimitDecision(False, retry)
            hits.append(now)
            self._hits[key] = hits
            return LimitDecision(True, 1)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class IdempotencyStore:
    """Replay POST results for the same workspace + route + Idempotency-Key."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()

    def begin(self, key: str) -> dict[str, Any] | None:
        """Mark in-flight. Returns an existing record if this key was already seen."""
        stamp = utc_now()
        with self._lock:
            rows = self._load()
            existing = rows.get(key)
            if existing is not None:
                return existing
            rows[key] = {
                "state": "pending",
                "status_code": 0,
                "body": None,
                "created_utc": stamp,
            }
            self._save(rows)
            return None

    def finish(self, key: str, *, status_code: int, body: dict[str, Any]) -> None:
        with self._lock:
            rows = self._load()
            rec = rows.get(key) or {}
            rec["state"] = "done"
            rec["status_code"] = int(status_code)
            rec["body"] = body
            rec["created_utc"] = rec.get("created_utc") or utc_now()
            rows[key] = rec
            self._save(rows)

    def drop(self, key: str) -> None:
        with self._lock:
            rows = self._load()
            rows.pop(key, None)
            self._save(rows)

    def _load(self) -> dict[str, dict[str, Any]]:
        if not os.path.isfile(self._path):
            return {}
        try:
            with open(self._path, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            return {}
        if not isinstance(raw, dict):
            return {}
        items = raw.get("items") if isinstance(raw.get("items"), dict) else raw
        if not isinstance(items, dict):
            return {}
        cutoff = utc_now()
        # ISO Z timestamps compare lexicographically for the same format.
        out: dict[str, dict[str, Any]] = {}
        for key, rec in items.items():
            if not isinstance(key, str) or not isinstance(rec, dict):
                continue
            created = str(rec.get("created_utc") or "")
            if created and _expired(created, cutoff):
                continue
            out[key] = rec
        return out

    def _save(self, rows: dict[str, dict[str, Any]]) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=os.path.dirname(self._path) or ".", prefix=".api-idem-", suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"items": rows}, f, indent=2)
            os.replace(tmp_path, self._path)
        except Exception:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise


def rate_for_read(windows: SlidingWindow, *, key_id: str, workspace_id: str) -> LimitDecision:
    first = windows.hit(f"key:{key_id}:read", READS_PER_KEY_MIN)
    if not first.allowed:
        return first
    return windows.hit(f"ws:{workspace_id}:read", READS_PER_WORKSPACE_MIN)


def rate_for_pack(windows: SlidingWindow, *, key_id: str, workspace_id: str) -> LimitDecision:
    first = windows.hit(f"key:{key_id}:pack", PACKS_PER_KEY_MIN)
    if not first.allowed:
        return first
    return windows.hit(f"ws:{workspace_id}:pack", PACKS_PER_WORKSPACE_MIN)


def rate_for_export(windows: SlidingWindow, *, key_id: str, workspace_id: str) -> LimitDecision:
    first = windows.hit(f"key:{key_id}:export", EXPORTS_PER_KEY_MIN)
    if not first.allowed:
        return first
    return windows.hit(f"ws:{workspace_id}:export", EXPORTS_PER_WORKSPACE_MIN)


def rate_for_auth_fail(windows: SlidingWindow, ip: str) -> LimitDecision:
    return windows.hit(f"ip:{ip or 'unknown'}:auth", AUTH_FAIL_MAX, window_s=AUTH_FAIL_WINDOW_S)


def auth_fail_blocked(windows: SlidingWindow, ip: str) -> LimitDecision:
    return windows.blocked(f"ip:{ip or 'unknown'}:auth", AUTH_FAIL_MAX, window_s=AUTH_FAIL_WINDOW_S)
