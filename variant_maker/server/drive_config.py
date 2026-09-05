from __future__ import annotations
import json
import os
from dataclasses import dataclass
from typing import Literal, Mapping

from .drive_oauth import OAuthTokenStore, oauth_client_configured

ENV_SA_JSON = "VARIANT_DRIVE_SERVICE_ACCOUNT_JSON"
ENV_OAUTH_CLIENT_ID = "VARIANT_DRIVE_OAUTH_CLIENT_ID"
ENV_OAUTH_CLIENT_SECRET = "VARIANT_DRIVE_OAUTH_CLIENT_SECRET"
ENV_OAUTH_REDIRECT_URI = "VARIANT_DRIVE_OAUTH_REDIRECT_URI"
ENV_SHARE_EMAIL = "VARIANT_DRIVE_SHARE_EMAIL"
# Branded mailbox is opt-in via VARIANT_DRIVE_SHARE_EMAIL. Until Jeff is ready,
# Studio shares whatever account is actually connected (snaughtyllc@gmail.com).
DEFAULT_SHARE_EMAIL = ""

DriveStatus = Literal["ready", "not_configured", "auth_failed"]
AuthMode = Literal["oauth", "service_account"]


@dataclass(frozen=True)
class DriveConfigInfo:
    status: DriveStatus
    sa_email: str | None
    message: str
    auth_mode: AuthMode | None = None
    connected_email: str | None = None
    oauth_available: bool = False


def read_share_email(environ: Mapping[str, str] | None = None) -> str:
    """Optional branded mailbox override. Empty means use the connected Drive account."""
    env = environ if environ is not None else os.environ
    raw = (env.get(ENV_SHARE_EMAIL) or "").strip()
    return raw or DEFAULT_SHARE_EMAIL


def effective_share_email(
    info: DriveConfigInfo,
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """Address operators should share folders with right now."""
    return read_share_email(environ) or info.connected_email or info.sa_email


def list_oauth_token_paths(data_dir: str, current: str | None = None) -> list[str]:
    """Workspace token first, then other tenant tokens on this Studio volume."""
    out: list[str] = []

    def add(path: str) -> None:
        abs_path = os.path.abspath(path)
        if abs_path not in out:
            out.append(abs_path)

    if current:
        add(current)
    root = os.path.abspath(data_dir)
    tenants = os.path.join(root, "tenants")
    if os.path.isdir(tenants):
        for name in sorted(os.listdir(tenants)):
            add(os.path.join(tenants, name, "drive", "oauth_token.json"))
    add(os.path.join(root, "drive", "oauth_token.json"))
    return out


def pick_oauth_token_path(
    data_dir: str,
    current: str | None,
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """Prefer the company mailbox token so every workspace uses studio@."""
    env = environ if environ is not None else os.environ
    share = read_share_email(env).lower()
    ready: list[tuple[str, str]] = []
    for path in list_oauth_token_paths(data_dir, current):
        if not os.path.isfile(path):
            continue
        info = resolve_drive_status(None, oauth_token_path=path, environ=env)
        if info.status == "ready" and info.auth_mode == "oauth":
            ready.append((path, (info.connected_email or "").lower()))
    if share:
        for path, email in ready:
            if email == share:
                return path
        return None
    if current:
        current_abs = os.path.abspath(current)
        for path, _email in ready:
            if path == current_abs:
                return path
    if ready:
        return ready[0][0]
    return current


def read_sa_email(sa_json_path: str) -> str | None:
    try:
        with open(sa_json_path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    email = data.get("client_email") if isinstance(data, dict) else None
    return email if isinstance(email, str) and email else None


def _sa_info(path: str) -> DriveConfigInfo:
    if not os.path.isfile(path):
        return DriveConfigInfo(
            "auth_failed", None,
            f"Drive service account JSON unreadable: {path}",
            oauth_available=False,
        )
    email = read_sa_email(path)
    if email is None:
        return DriveConfigInfo(
            "auth_failed", None,
            f"Drive service account JSON invalid or missing client_email: {path}",
            oauth_available=False,
        )
    return DriveConfigInfo(
        "ready", email, "Drive ready",
        auth_mode="service_account",
        connected_email=email,
        oauth_available=False,
    )


def resolve_drive_status(
    sa_json_path: str | None = None,
    *,
    oauth_token_path: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> DriveConfigInfo:
    """Resolve Studio Drive readiness.

    Preference order: usable OAuth refresh token → service account JSON → not configured.
    """
    env = environ if environ is not None else os.environ
    oauth_ok = oauth_client_configured(env)

    if oauth_token_path:
        store = OAuthTokenStore(oauth_token_path)
        if store.exists():
            email = store.read_email()
            try:
                data = store.load()
            except (OSError, json.JSONDecodeError, ValueError):
                return DriveConfigInfo(
                    "auth_failed", None,
                    f"Drive OAuth token unreadable: {oauth_token_path}",
                    oauth_available=oauth_ok,
                )
            if not data.get("refresh_token") and not data.get("token"):
                return DriveConfigInfo(
                    "auth_failed", None,
                    f"Drive OAuth token missing credentials: {oauth_token_path}",
                    oauth_available=oauth_ok,
                )
            return DriveConfigInfo(
                "ready", email, "Drive ready (Google OAuth)",
                auth_mode="oauth",
                connected_email=email,
                oauth_available=True,
            )

    path = sa_json_path if sa_json_path is not None else env.get(ENV_SA_JSON)
    if path:
        info = _sa_info(path)
        return DriveConfigInfo(
            info.status, info.sa_email, info.message,
            auth_mode=info.auth_mode,
            connected_email=info.connected_email,
            oauth_available=oauth_ok,
        )

    if oauth_ok:
        return DriveConfigInfo(
            "not_configured", None,
            "Drive not connected — Connect Google in Settings",
            oauth_available=True,
        )
    return DriveConfigInfo(
        "not_configured", None,
        "Drive not configured — Connect Google (OAuth) or set VARIANT_DRIVE_SERVICE_ACCOUNT_JSON",
        oauth_available=False,
    )
