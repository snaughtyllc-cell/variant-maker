from __future__ import annotations
import json
import os
from dataclasses import dataclass
from typing import Literal, Mapping

ENV_SA_JSON = "VARIANT_DRIVE_SERVICE_ACCOUNT_JSON"
DriveStatus = Literal["ready", "not_configured", "auth_failed"]


@dataclass(frozen=True)
class DriveConfigInfo:
    status: DriveStatus
    sa_email: str | None
    message: str


def read_sa_email(sa_json_path: str) -> str | None:
    try:
        with open(sa_json_path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    email = data.get("client_email") if isinstance(data, dict) else None
    return email if isinstance(email, str) and email else None


def resolve_drive_status(
    sa_json_path: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> DriveConfigInfo:
    env = environ if environ is not None else os.environ
    path = sa_json_path if sa_json_path is not None else env.get(ENV_SA_JSON)
    if not path:
        return DriveConfigInfo(
            "not_configured", None,
            "Drive not configured — set VARIANT_DRIVE_SERVICE_ACCOUNT_JSON",
        )
    if not os.path.isfile(path):
        return DriveConfigInfo(
            "auth_failed", None,
            f"Drive service account JSON unreadable: {path}",
        )
    email = read_sa_email(path)
    if email is None:
        return DriveConfigInfo(
            "auth_failed", None,
            f"Drive service account JSON invalid or missing client_email: {path}",
        )
    return DriveConfigInfo("ready", email, "Drive ready")
