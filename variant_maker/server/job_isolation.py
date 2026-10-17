"""Per-job isolation contract. PURE: no ffmpeg, no RunPod, no Drive HTTP.

Durable authority is the job record, not occupancy:

``(tenant_id, job_id, current_attempt_id, fencing_token, status)``

Attempts own immutable staged artifacts. The control plane owns publication
and deletion. ``source_id`` is a label, not authorization.

Legacy ``inputs/{source_id}/`` keys stay readable through an authorized job
record; copy them into the namespaced prefix before a new attempt uses them.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

TERMINAL_SUCCESS = frozenset({"completed", "done"})
KIND_PUBLISH = "publish"
KIND_INPUT_READ = "input_read"


class IsolationError(ValueError):
    """Invalid tenant/job/attempt/path component."""


def safe_id(value: str, *, name: str = "id") -> str:
    raw = str(value or "").strip()
    if not raw or raw in (".", "..") or "/" in raw or "\\" in raw or "\x00" in raw:
        raise IsolationError(f"invalid {name}")
    if raw != os.path.basename(raw):
        raise IsolationError(f"invalid {name}")
    return raw


def _artifact(name: str) -> str:
    base = os.path.basename(str(name or ""))
    if not base or base in (".", ".."):
        return "video.mp4"
    return base


def job_prefix(tenant_id: str, job_id: str) -> str:
    tenant = safe_id(tenant_id, name="tenant_id")
    job = safe_id(job_id, name="job_id")
    return f"tenants/{tenant}/jobs/{job}"


def namespaced_input_key(
    tenant_id: str, job_id: str, source_id: str, artifact_id: str,
) -> str:
    src = safe_id(source_id, name="source_id")
    return f"{job_prefix(tenant_id, job_id)}/inputs/{src}/{_artifact(artifact_id)}"


def attempt_output_key(
    tenant_id: str, job_id: str, attempt_id: str, source_id: str, artifact_id: str,
) -> str:
    attempt = safe_id(attempt_id, name="attempt_id")
    src = safe_id(source_id, name="source_id")
    return (
        f"{job_prefix(tenant_id, job_id)}/attempts/{attempt}/outputs/"
        f"{src}/{_artifact(artifact_id)}"
    )


def attempt_draft_key(tenant_id: str, job_id: str, attempt_id: str) -> str:
    attempt = safe_id(attempt_id, name="attempt_id")
    return f"{job_prefix(tenant_id, job_id)}/attempts/{attempt}/manifest.draft.json"


def publication_manifest_key(tenant_id: str, job_id: str, publication_id: str) -> str:
    pub = safe_id(publication_id, name="publication_id")
    return f"{job_prefix(tenant_id, job_id)}/manifests/{pub}.json"


def authorize_object_key(key: str, *, tenant_id: str, job_id: str) -> bool:
    """True only if the key sits under this tenant/job prefix. Not source_id."""
    prefix = job_prefix(tenant_id, job_id) + "/"
    raw = str(key or "")
    if not raw.startswith(prefix):
        return False
    rest = raw[len(prefix):]
    return bool(rest) and not rest.startswith("/") and ".." not in rest.split("/")


def is_legacy_object_key(key: str) -> bool:
    raw = str(key or "")
    return raw.startswith(("inputs/", "outputs/"))


def create_only_ok(*, existing_checksum: str | None, new_checksum: str) -> bool:
    if existing_checksum is None:
        return True
    return str(existing_checksum) == str(new_checksum)


def attempt_scratch_root(
    tmp_root: str,
    tenant_id: str,
    job_id: str,
    attempt_id: str,
    *,
    random_dir: str,
) -> str:
    """mkdtemp belongs *under* this attempt directory — never a global /out."""
    rnd = safe_id(random_dir, name="scratch")
    parts = (
        os.path.abspath(tmp_root),
        "tenants",
        safe_id(tenant_id, name="tenant_id"),
        "jobs",
        safe_id(job_id, name="job_id"),
        "attempts",
        safe_id(attempt_id, name="attempt_id"),
        rnd,
    )
    return os.path.join(*parts)


def drive_binding(
    *,
    tenant_id: str,
    job_id: str,
    workspace_id: str,
    drive_credential_ref: str,
    drive_account_id: str,
    destination_folder_id: str,
    destination_revision: int,
) -> dict[str, Any]:
    return {
        "tenant_id": safe_id(tenant_id, name="tenant_id"),
        "job_id": safe_id(job_id, name="job_id"),
        "workspace_id": safe_id(workspace_id, name="workspace_id"),
        "drive_credential_ref": str(drive_credential_ref or "").strip(),
        "drive_account_id": str(drive_account_id or "").strip(),
        "destination_folder_id": str(destination_folder_id or "").strip(),
        "destination_revision": int(destination_revision),
    }


def worker_may_hold_drive_token(purpose: str) -> bool:
    """Workers never get Drive OAuth. Control plane publishes from staged objects."""
    _ = purpose
    return False


def finalize_allowed(
    *,
    status: str,
    attempt_id: str,
    fence: str,
    current_attempt_id: str,
    current_fence: str,
    cancel_requested: bool,
) -> str:
    if str(status or "") in TERMINAL_SUCCESS:
        return "already_completed"
    if attempt_id != current_attempt_id or fence != current_fence:
        return "fenced"
    if cancel_requested:
        return "cancelled"
    return "ok"


def cancel_outcome(status: str) -> str:
    if str(status or "") in TERMINAL_SUCCESS:
        return "already_completed"
    return "cancel_requested"


# None = keep until explicit authorized deletion.
RETAIN: dict[str, dict[str, timedelta | None]] = {
    "worker_scratch": {
        "completed": timedelta(0),
        "cancelled": timedelta(0),
    },
    "local_media_cache": {
        "completed": timedelta(0),
        "cancelled": timedelta(hours=24),
    },
    "object_inputs": {
        "completed": timedelta(days=7),
        "cancelled": timedelta(days=7),
    },
    "selected_outputs": {
        "completed": timedelta(days=7),
        "cancelled": timedelta(hours=24),
    },
    "superseded_attempt_outputs": {
        "completed": timedelta(hours=24),
        "cancelled": timedelta(hours=24),
    },
    "job_records": {
        "completed": timedelta(days=30),
        "cancelled": timedelta(days=30),
        "failed": timedelta(days=30),
    },
    "published_drive_files": {
        "completed": None,
        "cancelled": None,
    },
}


def retain_until(
    kind: str,
    outcome: str,
    *,
    now: datetime,
) -> datetime | None:
    table = RETAIN[kind]
    key = str(outcome or "completed")
    if key == "failed" and "failed" not in table:
        key = "cancelled"
    if key not in table:
        key = "completed" if "completed" in table else next(iter(table))
    delta = table[key]
    if delta is None:
        return None
    return now + delta


def may_delete_abandoned_scratch(*, process_owns: bool) -> bool:
    """Startup janitor: never remove a directory a live process still owns."""
    return not bool(process_owns)
