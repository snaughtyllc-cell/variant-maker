"""Google OAuth for Studio Drive export (company admin-once refresh token on Pod).

Stores Google authorized-user JSON at `{workspace}/drive/oauth_token.json` so the
same `GoogleDrive(oauth_token=…)` path used by the farm works without an SA key.
"""
from __future__ import annotations

import json
import os
import secrets
import tempfile
from typing import Any, Callable, Mapping
from urllib.parse import urlencode

# Enough to upload into folders the signed-in user can already access (paste-folder flow).
# drive.file alone cannot write to arbitrary folder IDs the app did not create.
OAUTH_SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"


ExchangeFn = Callable[..., dict[str, Any]]
FetchEmailFn = Callable[[dict[str, Any]], str | None]


class OAuthTokenStore:
    """JSON file of Google authorized-user credentials (+ optional `email` field)."""

    def __init__(self, path: str) -> None:
        self._path = path

    @property
    def path(self) -> str:
        return self._path

    def exists(self) -> bool:
        return os.path.isfile(self._path)

    def load(self) -> dict[str, Any]:
        with open(self._path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("oauth token file must be a JSON object")
        return data

    def save(self, data: Mapping[str, Any]) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=os.path.dirname(self._path) or ".", prefix=".oauth-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(dict(data), f, indent=2)
            os.replace(tmp, self._path)
        except Exception:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise

    def clear(self) -> None:
        try:
            os.remove(self._path)
        except FileNotFoundError:
            pass

    def read_email(self) -> str | None:
        if not self.exists():
            return None
        try:
            email = self.load().get("email")
        except (OSError, json.JSONDecodeError, ValueError):
            return None
        return email if isinstance(email, str) and email else None


def build_authorization_url(
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    scopes: list[str] | None = None,
) -> str:
    scope = " ".join(scopes or OAUTH_SCOPES)
    qs = urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    })
    return f"{AUTH_URI}?{qs}"


def new_oauth_state() -> str:
    return secrets.token_urlsafe(24)


def resolve_redirect_uri(
    environ: Mapping[str, str],
    *,
    request_base: str | None = None,
    explicit: str | None = None,
) -> str:
    """Prefer explicit / env override; else `{request_base}/api/drive/oauth/callback`."""
    if explicit:
        return explicit.rstrip("/")
    env_uri = environ.get("VARIANT_DRIVE_OAUTH_REDIRECT_URI")
    if env_uri:
        return env_uri.rstrip("/")
    if request_base:
        return f"{request_base.rstrip('/')}/api/drive/oauth/callback"
    return "http://127.0.0.1:8000/api/drive/oauth/callback"


def public_request_base(headers: Mapping[str, str], fallback: str) -> str:
    """Build public origin from RunPod / reverse-proxy forwarded headers when present."""
    proto = headers.get("x-forwarded-proto") or headers.get("X-Forwarded-Proto")
    host = headers.get("x-forwarded-host") or headers.get("X-Forwarded-Host")
    if not host:
        host = headers.get("host") or headers.get("Host")
    if proto and host:
        # First value if comma-separated
        proto = proto.split(",")[0].strip()
        host = host.split(",")[0].strip()
        return f"{proto}://{host}"
    return fallback.rstrip("/")


def exchange_code_for_token(
    *,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict[str, Any]:
    """Exchange auth code for tokens; returns authorized-user dict for GoogleDrive."""
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": AUTH_URI,
                "token_uri": TOKEN_URI,
            }
        },
        scopes=OAUTH_SCOPES,
        redirect_uri=redirect_uri,
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    data = json.loads(creds.to_json())
    # Ensure refresh_token key exists for headless refresh
    if not data.get("refresh_token") and creds.refresh_token:
        data["refresh_token"] = creds.refresh_token
    return data


def fetch_connected_email(token_data: Mapping[str, Any]) -> str | None:
    """Best-effort email via Drive about.get (needs drive scope)."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_info(dict(token_data), OAUTH_SCOPES)
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    about = service.about().get(fields="user").execute()
    user = about.get("user") or {}
    email = user.get("emailAddress")
    return email if isinstance(email, str) and email else None


def oauth_client_configured(environ: Mapping[str, str]) -> bool:
    return bool(environ.get("VARIANT_DRIVE_OAUTH_CLIENT_ID") and
                environ.get("VARIANT_DRIVE_OAUTH_CLIENT_SECRET"))
