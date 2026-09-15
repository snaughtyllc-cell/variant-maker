"""Process-wide Fast slot journal. Survives a Railway restart without Redis.

Occupied / idle / unknown match the Wave 2 idle policy. Missing heartbeats
do not prove a slot is free — reconcile with the provider first. Pause
dispatch until every unknown slot is resolved or an untracked provider job
is accounted for.

Pack execution state stays on the tenant-scoped job. This file only records
which Fast slot (if any) a ``(tenant_id, job_id, attempt, fence)`` holds.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass

from .fast_idle import FAST_MAX_WORKERS, STATE_IDLE, STATE_OCCUPIED, STATE_UNKNOWN

JOURNAL_NAME = "fast_occupancy.json"


@dataclass
class SlotRecord:
    slot: int
    state: str = STATE_IDLE
    tenant_id: str | None = None
    job_id: str | None = None
    attempt_id: str | None = None
    fence: str | None = None
    provider_job_id: str | None = None
    worker_id: str | None = None
    boot_id: str | None = None
    kind: str = "fast"
    lease_expiry_utc: str | None = None
    heartbeat_utc: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    def clear(self) -> None:
        self.state = STATE_IDLE
        self.tenant_id = None
        self.job_id = None
        self.attempt_id = None
        self.fence = None
        self.provider_job_id = None
        self.worker_id = None
        self.boot_id = None
        self.kind = "fast"
        self.lease_expiry_utc = None
        self.heartbeat_utc = None


def _empty_slots(n: int) -> list[SlotRecord]:
    return [SlotRecord(slot=i) for i in range(n)]


class OccupancyJournal:
    def __init__(self, path: str, *, n_slots: int = FAST_MAX_WORKERS) -> None:
        self.path = os.path.abspath(path)
        self._n = max(1, int(n_slots))
        self._lock = threading.Lock()
        self._pause_dispatch = False
        self._slots = _empty_slots(self._n)
        self.load()

    def load(self) -> dict:
        if not os.path.isfile(self.path):
            return self.snapshot()
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return self.snapshot()
        if not isinstance(data, dict):
            return self.snapshot()
        rows = data.get("slots") or []
        slots = _empty_slots(self._n)
        if isinstance(rows, list):
            for raw in rows:
                if not isinstance(raw, dict):
                    continue
                try:
                    idx = int(raw.get("slot"))
                except (TypeError, ValueError):
                    continue
                if idx < 0 or idx >= self._n:
                    continue
                slots[idx] = SlotRecord(
                    slot=idx,
                    state=str(raw.get("state") or STATE_IDLE),
                    tenant_id=raw.get("tenant_id"),
                    job_id=raw.get("job_id"),
                    attempt_id=raw.get("attempt_id"),
                    fence=raw.get("fence"),
                    provider_job_id=raw.get("provider_job_id"),
                    worker_id=raw.get("worker_id"),
                    boot_id=raw.get("boot_id"),
                    kind=str(raw.get("kind") or "fast"),
                    lease_expiry_utc=raw.get("lease_expiry_utc"),
                    heartbeat_utc=raw.get("heartbeat_utc"),
                )
        with self._lock:
            self._slots = slots
            self._pause_dispatch = bool(data.get("pause_dispatch") or False)
        return self.snapshot()

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "pause_dispatch": self._pause_dispatch,
                "slots": [s.to_dict() for s in self._slots],
            }

    def can_dispatch(self) -> bool:
        with self._lock:
            return not self._pause_dispatch

    def _persist_unlocked(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        payload = {
            "pause_dispatch": self._pause_dispatch,
            "slots": [s.to_dict() for s in self._slots],
        }
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.replace(tmp, self.path)

    def occupy(
        self,
        slot: int,
        *,
        tenant_id: str,
        job_id: str,
        attempt_id: str,
        fence: str,
        provider_job_id: str | None = None,
        worker_id: str | None = None,
        boot_id: str | None = None,
        kind: str = "fast",
        lease_expiry_utc: str | None = None,
    ) -> SlotRecord:
        with self._lock:
            rec = self._slots[int(slot)]
            rec.state = STATE_OCCUPIED
            rec.tenant_id = tenant_id
            rec.job_id = job_id
            rec.attempt_id = attempt_id
            rec.fence = fence
            rec.provider_job_id = provider_job_id
            rec.worker_id = worker_id
            rec.boot_id = boot_id
            rec.kind = kind
            rec.lease_expiry_utc = lease_expiry_utc
            self._persist_unlocked()
            return SlotRecord(**rec.to_dict())

    def release(self, slot: int, *, fence: str) -> bool:
        with self._lock:
            rec = self._slots[int(slot)]
            if rec.fence != fence:
                return False
            rec.clear()
            self._persist_unlocked()
            return True

    def on_process_start(self) -> dict:
        """Pause dispatch. Occupied slots become unknown until provider reconcile."""
        with self._lock:
            self._pause_dispatch = True
            for rec in self._slots:
                if rec.state == STATE_OCCUPIED or rec.job_id:
                    rec.state = STATE_UNKNOWN
            self._persist_unlocked()
        return self.snapshot()

    def reconcile(self, running_provider_ids: set[str] | None = None) -> dict:
        running = {str(x) for x in (running_provider_ids or set()) if str(x).strip()}
        with self._lock:
            tracked: set[str] = set()
            unresolved = False
            for rec in self._slots:
                pid = rec.provider_job_id
                if pid:
                    tracked.add(pid)
                if rec.state == STATE_IDLE and not rec.job_id:
                    continue
                if pid and pid in running:
                    rec.state = STATE_OCCUPIED
                elif pid and pid not in running:
                    rec.clear()
                elif rec.state == STATE_UNKNOWN or rec.job_id:
                    rec.state = STATE_UNKNOWN
                    unresolved = True
            extra = running - tracked
            self._pause_dispatch = bool(extra) or unresolved
            self._persist_unlocked()
        return self.snapshot()
