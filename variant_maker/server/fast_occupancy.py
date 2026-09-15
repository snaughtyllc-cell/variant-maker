"""Two scale-to-zero Fast CPU slots. One complete pack per worker.

PURE scheduler: no ffmpeg, no RunPod. Occupancy is process-wide so two
workspaces cannot claim the same slot. Pack execution state stays on the
tenant-scoped job — this module only leases workers.

Reservations are atomic (one ``threading.Lock``). Simultaneous submits
cannot both take slot 0.
"""
from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass

FAST_SLOTS = 2
KIND_FAST = "fast"
KIND_HQ = "hq"
FAST_ENDPOINT_ENV = "RUNPOD_FAST_ENDPOINT_ID"
FAST_OVERFLOW_ENV = "RUNPOD_FAST_ENDPOINT_ID_2"


@dataclass(frozen=True)
class Reservation:
    tenant_id: str
    job_id: str
    kind: str
    slot: int | None
    attempt_id: str
    fence: str
    endpoint_id: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def occupancy_from_env(environ: Mapping[str, str] | None = None) -> FastOccupancy:
    """Primary Fast endpoint on slot 0; optional second id on slot 1.

    When ``RUNPOD_FAST_ENDPOINT_ID_2`` is unset, both slots share the primary
    id (one RunPod endpoint with max workers ≥ 2). Occupancy still caps
    in-flight Fast packs at two.
    """
    env = os.environ if environ is None else environ
    primary = (env.get(FAST_ENDPOINT_ENV) or "").strip() or None
    overflow = (env.get(FAST_OVERFLOW_ENV) or "").strip() or None
    ids = [primary, overflow if overflow else primary]
    return FastOccupancy(fast_slots=FAST_SLOTS, endpoint_ids=ids)


class FastOccupancy:
    """Up to two Fast CPU workers. Each studio holds at most one running pack.

    Slot 0 is the primary Fast endpoint. Slot 1 is the overflow worker (same
    endpoint if the platform can schedule two workers, or a second endpoint
    id). HQ does not consume a Fast slot but still takes the studio lock.
    """

    def __init__(
        self,
        *,
        fast_slots: int = FAST_SLOTS,
        endpoint_ids: list[str | None] | None = None,
    ) -> None:
        n = max(1, int(fast_slots))
        self._slots: list[Reservation | None] = [None] * n
        ids = list(endpoint_ids or [])
        while len(ids) < n:
            ids.append(ids[-1] if ids else None)
        self._endpoint_ids = ids[:n]
        self._tenant_job: dict[str, str] = {}
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)

    @property
    def fast_slots(self) -> int:
        return len(self._slots)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "fast_slots": [
                    None if r is None else r.to_dict() for r in self._slots
                ],
                "tenants": dict(self._tenant_job),
            }

    def try_begin(
        self,
        tenant_id: str,
        job_id: str,
        *,
        need_fast_slot: bool,
    ) -> Reservation | None:
        """Atomic reserve. None → caller waits or stays queued. Never splits a pack."""
        tenant = str(tenant_id or "").strip() or "local"
        job = str(job_id or "").strip()
        if not job:
            return None
        with self._cv:
            held = self._tenant_job.get(tenant)
            if held is not None and held != job:
                return None
            slot: int | None = None
            kind = KIND_HQ
            if need_fast_slot:
                kind = KIND_FAST
                for i, occ in enumerate(self._slots):
                    if occ is None or (occ.tenant_id == tenant and occ.job_id == job):
                        slot = i
                        break
                if slot is None:
                    return None
            res = Reservation(
                tenant_id=tenant,
                job_id=job,
                kind=kind,
                slot=slot,
                attempt_id=uuid.uuid4().hex[:12],
                fence=uuid.uuid4().hex,
                endpoint_id=None if slot is None else self._endpoint_ids[slot],
            )
            self._tenant_job[tenant] = job
            if slot is not None:
                self._slots[slot] = res
            return res

    def wait(self, timeout: float = 0.25) -> None:
        with self._cv:
            self._cv.wait(timeout=max(0.0, float(timeout)))

    def _fast_for_job(self, job_id: str) -> Reservation | None:
        for occ in self._slots:
            if occ is not None and occ.job_id == job_id:
                return occ
        return None

    def release(self, reservation: Reservation | None) -> bool:
        """Release only the matching fence. Stale attempts cannot free another job's slot."""
        if reservation is None:
            return False
        with self._cv:
            tenant = reservation.tenant_id
            held = self._tenant_job.get(tenant)
            if held != reservation.job_id:
                return False
            if reservation.slot is not None:
                if reservation.slot < 0 or reservation.slot >= len(self._slots):
                    return False
                current = self._slots[reservation.slot]
                if current is None or current.fence != reservation.fence:
                    return False
                self._slots[reservation.slot] = None
            else:
                newer = self._fast_for_job(reservation.job_id)
                if newer is not None and newer.fence != reservation.fence:
                    return False
            del self._tenant_job[tenant]
            self._cv.notify_all()
            return True
