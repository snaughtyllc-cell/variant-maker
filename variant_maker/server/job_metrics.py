"""Per-job RunPod timing, bytes, endpoint, and estimated cost.

Persisted on job.json and copied onto the usage.jsonl row so pricing can be
defended without PostHog. Missing probe/ffmpeg never fails a job.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

FAST_USD_PER_HOUR = 0.58
HQ_USD_PER_HOUR = 1.50  # 4090-class estimate; override via env
FAST_USD_ENV = "VARIANT_RUNPOD_FAST_USD_PER_HOUR"
HQ_USD_ENV = "VARIANT_RUNPOD_HQ_USD_PER_HOUR"

ProbeFn = Callable[[str], Any]


@dataclass
class JobTelemetry:
    workspace_id: str | None = None
    customer_email: str | None = None
    runpod_job_id: str | None = None
    runpod_endpoint_id: str | None = None
    requested: int = 0
    submitted_utc: str | None = None
    started_utc: str | None = None
    completed_utc: str | None = None
    shutdown_utc: str | None = None
    retry_count: int = 0
    regen_count: int = 0
    input_bytes: int = 0
    output_bytes: int = 0
    railway_media_bytes: int = 0
    delivery_destination: str = "download"
    runpod_cost_usd: float | None = None
    processing_charge: str | None = None
    source: dict[str, Any] | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def telemetry_to_dict(tel: JobTelemetry | dict | None) -> dict[str, Any]:
    if tel is None:
        return {}
    if isinstance(tel, dict):
        return dict(tel)
    data = asdict(tel)
    extra = data.pop("extra", {}) or {}
    if extra:
        data.update(extra)
    return data


def merge_telemetry(existing: dict | None, **fields: Any) -> dict[str, Any]:
    out = dict(existing or {})
    for key, value in fields.items():
        if value is not None:
            out[key] = value
    return out


def usd_per_hour(quality_mode: str, environ: dict | None = None) -> float:
    env = os.environ if environ is None else environ
    if str(quality_mode or "").strip().lower() == "hq":
        raw = (env.get(HQ_USD_ENV) or "").strip()
        try:
            return float(raw) if raw else HQ_USD_PER_HOUR
        except ValueError:
            return HQ_USD_PER_HOUR
    raw = (env.get(FAST_USD_ENV) or "").strip()
    try:
        return float(raw) if raw else FAST_USD_PER_HOUR
    except ValueError:
        return FAST_USD_PER_HOUR


def estimate_runpod_cost(
    *,
    billed_seconds: float,
    quality_mode: str = "fast",
    usd_per_hour_rate: float | None = None,
    environ: dict | None = None,
) -> float:
    rate = usd_per_hour_rate
    if rate is None:
        rate = usd_per_hour(quality_mode, environ)
    seconds = max(0.0, float(billed_seconds or 0.0))
    return round((seconds / 3600.0) * float(rate), 6)


def _parse_utc(value: str | None):
    from datetime import UTC, datetime
    if not value:
        return None
    raw = str(value).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def billed_seconds(submitted_utc: str | None, completed_utc: str | None) -> float | None:
    start = _parse_utc(submitted_utc)
    end = _parse_utc(completed_utc)
    if start is None or end is None:
        return None
    return max(0.0, (end - start).total_seconds())


def processing_charge_label(
    quality_mode: str,
    count: int,
    *,
    prep_mode: str = "none",
) -> str:
    n = max(0, int(count or 0))
    if str(prep_mode or "").strip().lower() == "hq":
        return f"HQ reconstruct + Fast {n} pack"
    if str(quality_mode or "").strip().lower() == "hq":
        return f"HQ {n} pack"
    return f"Fast {n} pack"


def regen_count_from_variants(variants: list[Any]) -> int:
    total = 0
    for v in variants:
        quality = getattr(v, "quality", None)
        if not isinstance(quality, dict):
            continue
        try:
            total += int(quality.get("regen_count") or 0)
        except (TypeError, ValueError):
            continue
    return total


def source_snapshot(
    path: str,
    *,
    probe_fn: ProbeFn | None = None,
    codec: str | None = None,
) -> dict[str, Any]:
    """Bytes always; duration/geometry when probe works. Never raises."""
    filename = os.path.basename(path) if path else ""
    try:
        size = os.path.getsize(path) if path and os.path.isfile(path) else 0
    except OSError:
        size = 0
    snap: dict[str, Any] = {
        "filename": filename,
        "bytes": int(size),
        "duration_s": None,
        "width": None,
        "height": None,
        "codec": codec,
    }
    info = None
    try:
        fn = probe_fn if probe_fn is not None else _default_probe
        info = fn(path) if path else None
    except Exception:
        info = None
    if info is not None:
        snap["duration_s"] = getattr(info, "duration_s", None)
        snap["width"] = getattr(info, "width", None)
        snap["height"] = getattr(info, "height", None)
        if codec is None:
            snap["codec"] = getattr(info, "codec", None)
    return snap


def _default_probe(path: str):
    from variant_maker.probe import probe
    return probe(path, hash_content=False)


def finalize_telemetry(
    job: Any,
    *,
    now_utc: str,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Fill completion fields on an existing telemetry dict."""
    tel = dict(getattr(job, "telemetry", None) or {})
    if workspace_id and not tel.get("workspace_id"):
        tel["workspace_id"] = workspace_id
    tel["requested"] = int(job.count or 0)
    tel.setdefault("delivery_destination", "download")
    tel["completed_utc"] = now_utc
    tel["shutdown_utc"] = now_utc
    variants = [v for s in job.sources for v in s.variants]
    tel["regen_count"] = regen_count_from_variants(variants)
    charge = processing_charge_label(
        job.quality_mode, job.count, prep_mode=getattr(job, "prep_mode", "none"),
    )
    tel["processing_charge"] = charge
    submitted = tel.get("submitted_utc") or getattr(job, "created_utc", None)
    tel.setdefault("submitted_utc", submitted)
    seconds = billed_seconds(submitted, now_utc)
    if seconds is not None:
        tel["runpod_cost_usd"] = estimate_runpod_cost(
            billed_seconds=seconds, quality_mode=job.quality_mode,
        )
    return tel
