"""Pack critical-path timing. PURE — no ffmpeg.

Counts rejected uniqueness candidates, not only the encode that shipped.
Signatures tell Wave 2 whether wait is cold-start, encode, hunt, or upload.
Do not change uniqueness 24/24 here.
"""
from __future__ import annotations

from typing import Any

FAIL_STATUSES = ("uniqueness_fail", "corrupt")
SIGNATURES = (
    "cold_start_bound",
    "encode_bound",
    "hunt_bound",
    "queue_or_upload_bound",
    "mixed",
)


def new_accumulator() -> dict[str, Any]:
    return {
        "candidates": 0,
        "encode_s": 0.0,
        "uniqueness_s": 0.0,
        "quality_s": 0.0,
        "peer_s": 0.0,
        "rejected_encode_s": 0.0,
        "reject_reasons": [],
        "last_encode_s": 0.0,
    }


def add_encode(acc: dict[str, Any], seconds: float) -> None:
    s = max(0.0, float(seconds or 0.0))
    acc["candidates"] = int(acc.get("candidates") or 0) + 1
    acc["encode_s"] = float(acc.get("encode_s") or 0.0) + s
    acc["last_encode_s"] = s


def add_uniqueness(acc: dict[str, Any], seconds: float) -> None:
    acc["uniqueness_s"] = float(acc.get("uniqueness_s") or 0.0) + max(0.0, float(seconds or 0.0))


def add_peer(acc: dict[str, Any], seconds: float) -> None:
    acc["peer_s"] = float(acc.get("peer_s") or 0.0) + max(0.0, float(seconds or 0.0))


def add_quality(acc: dict[str, Any], seconds: float) -> None:
    acc["quality_s"] = float(acc.get("quality_s") or 0.0) + max(0.0, float(seconds or 0.0))


def mark_reject(acc: dict[str, Any], reason: str) -> None:
    acc.setdefault("reject_reasons", []).append(str(reason))
    acc["rejected_encode_s"] = float(acc.get("rejected_encode_s") or 0.0) + float(
        acc.get("last_encode_s") or 0.0
    )


def slot_from_acc(
    acc: dict[str, Any],
    *,
    index: int,
    status: str,
    elapsed_s: float,
    escalated: bool = False,
    autotune_iters: int | None = None,
) -> dict[str, Any]:
    """One variant's hunt, including encodes that did not ship."""
    candidates = int(acc.get("candidates") or 0)
    accepted = status not in FAIL_STATUSES
    reasons = [str(r) for r in (acc.get("reject_reasons") or [])]
    return {
        "index": int(index),
        "status": status,
        "candidates": candidates,
        "encode_s": round(float(acc.get("encode_s") or 0.0), 3),
        "uniqueness_s": round(float(acc.get("uniqueness_s") or 0.0), 3),
        "quality_s": round(float(acc.get("quality_s") or 0.0), 3),
        "peer_s": round(float(acc.get("peer_s") or 0.0), 3),
        "rejected_encode_s": round(float(acc.get("rejected_encode_s") or 0.0), 3),
        "reject_reasons": reasons,
        "accepted_on_candidate": candidates if accepted and candidates else None,
        "elapsed_s": round(max(0.0, float(elapsed_s or 0.0)), 3),
        "escalated": bool(escalated),
        "autotune_iters": autotune_iters,
    }


def summarize_pack(
    slots: list[dict[str, Any]],
    *,
    wall_s: float,
    startup_s: float | None = None,
    upload_s: float | None = None,
    cpu_s: float | None = None,
    maxrss_kb: int | None = None,
    jobs: int | None = None,
    worker_id: str | None = None,
) -> dict[str, Any]:
    """Roll variant hunt slots into a pack report. Timing successful encodes only is a miss."""
    rows = list(slots or [])
    candidates = sum(int(s.get("candidates") or 0) for s in rows)
    accepted = sum(1 for s in rows if s.get("status") not in FAIL_STATUSES)
    rejected = max(0, candidates - accepted)
    encode_s = sum(float(s.get("encode_s") or 0.0) for s in rows)
    uniqueness_s = sum(float(s.get("uniqueness_s") or 0.0) for s in rows)
    quality_s = sum(float(s.get("quality_s") or 0.0) for s in rows)
    peer_s = sum(float(s.get("peer_s") or 0.0) for s in rows)
    rejected_encode_s = sum(float(s.get("rejected_encode_s") or 0.0) for s in rows)
    time_to_accept = [
        float(s["elapsed_s"])
        for s in sorted(rows, key=lambda r: int(r.get("index") or 0))
        if s.get("status") not in FAIL_STATUSES and s.get("elapsed_s") is not None
    ]
    by_slot = [
        {
            "index": int(s.get("index") or 0),
            "candidates": int(s.get("candidates") or 0),
            "accepted": s.get("status") not in FAIL_STATUSES,
            "elapsed_s": s.get("elapsed_s"),
            "reject_reasons": list(s.get("reject_reasons") or []),
        }
        for s in sorted(rows, key=lambda r: int(r.get("index") or 0))
    ]
    attempts_per_accepted = (
        round(candidates / accepted, 3) if accepted else None
    )
    wall = round(max(0.0, float(wall_s or 0.0)), 3)
    out: dict[str, Any] = {
        "candidates": candidates,
        "accepted": accepted,
        "rejected_candidates": rejected,
        "attempts_per_accepted": attempts_per_accepted,
        "encode_s": round(encode_s, 3),
        "uniqueness_s": round(uniqueness_s, 3),
        "quality_s": round(quality_s, 3),
        "peer_s": round(peer_s, 3),
        "rejected_encode_s": round(rejected_encode_s, 3),
        "wall_s": wall,
        "time_to_first_s": round(time_to_accept[0], 3) if time_to_accept else None,
        "time_to_accept": [round(t, 3) for t in time_to_accept],
        "by_slot": by_slot,
        "startup_s": None if startup_s is None else round(float(startup_s), 3),
        "upload_s": None if upload_s is None else round(float(upload_s), 3),
        "cpu_s": None if cpu_s is None else round(float(cpu_s), 3),
        "maxrss_kb": None if maxrss_kb is None else int(maxrss_kb),
        "jobs": jobs,
        "worker_id": worker_id,
    }
    out["signature"] = classify_signature(out)
    return out


def classify_signature(summary: dict[str, Any]) -> str:
    """Name the dominant wait. None of these change uniqueness work."""
    wall = float(summary.get("wall_s") or 0.0)
    startup = summary.get("startup_s")
    upload = summary.get("upload_s")
    encode_s = float(summary.get("encode_s") or 0.0)
    uniqueness_s = float(summary.get("uniqueness_s") or 0.0)
    peer_s = float(summary.get("peer_s") or 0.0)
    rejected_encode_s = float(summary.get("rejected_encode_s") or 0.0)
    attempts = summary.get("attempts_per_accepted")
    hunt_s = uniqueness_s + peer_s + rejected_encode_s
    shipped_encode_s = max(0.0, encode_s - rejected_encode_s)

    if startup is not None and float(startup) >= 20.0 and (
        wall <= 0.0 or float(startup) >= 0.35 * max(wall, float(startup))
    ):
        return "cold_start_bound"
    if upload is not None and float(upload) >= 20.0 and wall > 0 and float(upload) >= 0.35 * wall:
        return "queue_or_upload_bound"
    huntish = (
        (attempts is not None and float(attempts) >= 1.4)
        or (hunt_s > 0 and hunt_s >= shipped_encode_s and hunt_s >= 0.35 * max(encode_s + uniqueness_s + peer_s, 1e-9))
    )
    if huntish and hunt_s >= shipped_encode_s:
        return "hunt_bound"
    if encode_s > 0 and shipped_encode_s >= hunt_s:
        return "encode_bound"
    return "mixed"


def worker_id(environ: dict | None = None) -> str | None:
    import os
    env = os.environ if environ is None else environ
    for key in ("RUNPOD_POD_ID", "HOSTNAME"):
        raw = (env.get(key) or "").strip()
        if raw:
            return raw
    return None
