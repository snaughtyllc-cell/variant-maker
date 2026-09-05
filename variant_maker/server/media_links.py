"""Object-storage key layout, signed-link TTLs, and output retention.

Legacy keys are ``inputs/{source_id}/`` and ``outputs/{source_id}/``.
``source_id`` is a label, not authorization. New writes use
``job_isolation.namespaced_*`` (tenant + job + attempt). Resolve a legacy
object only through an authorized job record, then copy it into the
namespaced prefix before a new attempt reads it.
"""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

DOWNLOAD_TTL_SECONDS = 15 * 60
UPLOAD_TTL_SECONDS = 60 * 60
# Direct-download outputs: 48h inside the 24–72h window. Drive-delivered
# objects are deleted after confirmed upload.
OUTPUT_KEEP_HOURS = 48
DRIVE_OUTPUT_KEEP_HOURS = 1
OUTPUT_KEEP_HOURS_ENV = "VARIANT_OUTPUT_KEEP_HOURS"
MULTIPART_THRESHOLD = 90 * 1024 * 1024
MULTIPART_PART_SIZE = 16 * 1024 * 1024


def _safe_name(name: str) -> str:
    base = os.path.basename(str(name or ""))
    if not base or base in (".", ".."):
        return "video.mp4"
    return base


def input_key(source_id: str, filename: str) -> str:
    return f"inputs/{source_id}/{_safe_name(filename)}"


def output_key(source_id: str, filename: str) -> str:
    return f"outputs/{source_id}/{_safe_name(filename)}"


def upload_key(upload_id: str, filename: str) -> str:
    return f"uploads/{upload_id}/{_safe_name(filename)}"


def is_direct_upload_key(key: str) -> bool:
    """True only for ``uploads/{id}/{basename}`` — never inputs/ or outputs/."""
    parts = str(key or "").split("/")
    if len(parts) != 3 or parts[0] != "uploads":
        return False
    upload_id, name = parts[1], parts[2]
    if not upload_id or upload_id != os.path.basename(upload_id) or upload_id in (".", ".."):
        return False
    return bool(name) and name == os.path.basename(name) and name not in (".", "..")


def package_zip_key(source_id: str) -> str:
    return f"outputs/{source_id}/variants.zip"


def output_keep_hours(environ: dict | None = None) -> float:
    env = os.environ if environ is None else environ
    raw = env.get(OUTPUT_KEEP_HOURS_ENV, str(OUTPUT_KEEP_HOURS))
    try:
        return max(0.0, float(str(raw).strip()))
    except (TypeError, ValueError):
        return float(OUTPUT_KEEP_HOURS)


def outputs_expire_utc(
    *,
    now: datetime | None = None,
    destination: str = "download",
    environ: dict | None = None,
) -> str:
    when = now or datetime.now(UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    hours = (
        DRIVE_OUTPUT_KEEP_HOURS
        if str(destination or "") == "google_drive"
        else output_keep_hours(environ)
    )
    exp = when + timedelta(hours=hours)
    return exp.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_jpeg_name(name: str | None) -> bool:
    base = os.path.basename(str(name or "")).lower()
    return base.endswith((".jpg", ".jpeg"))


def is_mp4_name(name: str | None) -> bool:
    return os.path.basename(str(name or "")).lower().endswith(".mp4")
