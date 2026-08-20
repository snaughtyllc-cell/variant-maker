"""Google OAuth for Studio Drive export (company admin-once refresh token on Pod).

Stores Google authorized-user JSON at `{workspace}/drive/oauth_token.json` so the
same `GoogleDrive(oauth_token=…)` path used by the farm works without an SA key.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import tempfile
import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlencode, urlparse

# Enough to upload into folders the signed-in user can already access (paste-folder flow).
# drive.file alone cannot write to arbitrary folder IDs the app did not create.
# spreadsheets: Drop Ledger (VaryForge Drop Ledger) durable platform labels.
OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

# Login only — Drive Connect stays a second consent with OAUTH_SCOPES.
LOGIN_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
ENV_LOGIN_REDIRECT_URI = "VARIANT_AUTH_OAUTH_REDIRECT_URI"

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


_PENDING_TTL_S = 15 * 60


class OAuthPendingStore:
    """CSRF states on disk so Connect Google survives a new API process / replica."""

    def __init__(self, path: str) -> None:
        self._path = path

    def add(self, state: str) -> None:
        data = self._load()
        now = time.time()
        data = {k: ts for k, ts in data.items() if now - ts < _PENDING_TTL_S}
        data[state] = now
        self._save(data)

    def consume(self, state: str) -> bool:
        data = self._load()
        now = time.time()
        data = {k: ts for k, ts in data.items() if now - ts < _PENDING_TTL_S}
        if state not in data:
            self._save(data)
            return False
        del data[state]
        self._save(data)
        return True

    def _load(self) -> dict[str, float]:
        if not os.path.isfile(self._path):
            return {}
        try:
            with open(self._path, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError):
            return {}
        if not isinstance(raw, dict):
            return {}
        out: dict[str, float] = {}
        for k, v in raw.items():
            if isinstance(k, str) and isinstance(v, (int, float)):
                out[k] = float(v)
        return out

    def _save(self, data: Mapping[str, float]) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=os.path.dirname(self._path) or ".", prefix=".oauth-pending-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(dict(data), f)
            os.replace(tmp, self._path)
        except Exception:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise


def studio_origin_from_redirect_uri(redirect_uri: str, fallback: str) -> str:
    """Public Studio origin for post-OAuth redirects (not the FastAPI bind host)."""
    parsed = urlparse(redirect_uri)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return fallback.rstrip("/")


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


def resolve_login_redirect_uri(
    environ: Mapping[str, str],
    *,
    request_base: str | None = None,
    explicit: str | None = None,
) -> str:
    """Prefer VARIANT_AUTH_OAUTH_REDIRECT_URI; else `{origin}/api/auth/google/callback`."""
    if explicit:
        return explicit.rstrip("/")
    env_uri = environ.get(ENV_LOGIN_REDIRECT_URI)
    if env_uri:
        return env_uri.rstrip("/")
    if request_base:
        return f"{request_base.rstrip('/')}/api/auth/google/callback"
    return "http://127.0.0.1:8000/api/auth/google/callback"


def login_profile_from_token(token_data: Mapping[str, Any]) -> tuple[str, str]:
    """Email + name from a Google token dict (`email`/`name` or `id_token` claims)."""
    email = token_data.get("email") if isinstance(token_data.get("email"), str) else None
    name = token_data.get("name") if isinstance(token_data.get("name"), str) else ""
    id_token = token_data.get("id_token")
    if isinstance(id_token, str) and id_token.count(".") >= 2:
        payload_b64 = id_token.split(".")[1]
        pad = "=" * (-len(payload_b64) % 4)
        try:
            payload = json.loads(base64.urlsafe_b64decode(payload_b64 + pad))
        except (OSError, json.JSONDecodeError, ValueError):
            payload = {}
        if isinstance(payload, dict):
            if not email and isinstance(payload.get("email"), str):
                email = payload["email"]
            if not name and isinstance(payload.get("name"), str):
                name = payload["name"]
            elif not name and isinstance(payload.get("given_name"), str):
                name = payload["given_name"]
    if not email:
        raise ValueError("Google login did not return an email")
    return email, name or email


def fetch_userinfo_profile(
    token_data: Mapping[str, Any],
    *,
    get_json: Callable[[str, Mapping[str, str]], Mapping[str, Any]] | None = None,
) -> tuple[str, str]:
    """Email + name from Google's userinfo endpoint using the access token."""
    access = token_data.get("token") or token_data.get("access_token")
    if not isinstance(access, str) or not access:
        raise ValueError("Google login did not return an email")

    def _get(url: str, headers: Mapping[str, str]) -> Mapping[str, Any]:
        from urllib.request import Request, urlopen
        req = Request(url, headers=dict(headers))
        with urlopen(req, timeout=15) as resp:
            raw = json.loads(resp.read().decode())
        if not isinstance(raw, dict):
            raise ValueError("Google login did not return an email")
        return raw

    body = (get_json or _get)(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        {"Authorization": f"Bearer {access}"},
    )
    email = body.get("email") if isinstance(body.get("email"), str) else None
    name = body.get("name") if isinstance(body.get("name"), str) else ""
    if not name and isinstance(body.get("given_name"), str):
        name = body["given_name"]
    if not email:
        raise ValueError("Google login did not return an email")
    return email, name or email


def resolve_login_profile(
    token_data: Mapping[str, Any],
    *,
    get_json: Callable[[str, Mapping[str, str]], Mapping[str, Any]] | None = None,
) -> tuple[str, str]:
    """Prefer id_token / email fields; fall back to userinfo."""
    try:
        return login_profile_from_token(token_data)
    except ValueError:
        return fetch_userinfo_profile(token_data, get_json=get_json)


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
    scopes: list[str] | None = None,
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
        scopes=list(scopes or OAUTH_SCOPES),
        redirect_uri=redirect_uri,
    )
    # Google often returns a slightly different granted-scope set than we asked
    # for (drive + drive.file + sheets). Default oauthlib then raises and Studio
    # looks like Connect never happened.
    os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
    os.environ.setdefault("OAUTHLIB_IGNORE_SCOPE_CHANGE", "1")
    flow.fetch_token(code=code)
    creds = flow.credentials
    data = json.loads(creds.to_json())
    # Ensure refresh_token key exists for headless refresh
    if not data.get("refresh_token") and creds.refresh_token:
        data["refresh_token"] = creds.refresh_token
    # to_json() omits OpenID id_token — login needs it (or userinfo) for email.
    id_token = getattr(creds, "id_token", None)
    if id_token and not data.get("id_token"):
        data["id_token"] = id_token
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
