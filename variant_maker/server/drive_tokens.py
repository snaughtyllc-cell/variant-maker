"""Short-lived Google Drive access tokens for RunPod — never the refresh token."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlencode

TOKEN_URI = "https://oauth2.googleapis.com/token"


class DriveTokenError(Exception):
    """Raised when a job-scoped Drive access token cannot be minted."""


PostFn = Callable[[str, bytes, dict[str, str]], dict[str, Any]]


def mint_access_token(
    token_data: Mapping[str, Any],
    *,
    client_id: str,
    client_secret: str,
    post_json: PostFn | None = None,
) -> dict[str, Any]:
    """Refresh into an access token. Return payload has no refresh_token."""
    refresh = token_data.get("refresh_token") or token_data.get("refreshToken")
    existing = token_data.get("token") or token_data.get("access_token")
    if not refresh and existing:
        out = {
            "access_token": str(existing),
            "expires_in": int(token_data.get("expiry") or token_data.get("expires_in") or 0),
            "token_type": "Bearer",
        }
        assert "refresh_token" not in out
        return out
    if not refresh:
        raise DriveTokenError("Drive is connected but has no refresh token — reconnect Google")
    if not client_id or not client_secret:
        raise DriveTokenError("OAuth client is not configured")
    body = urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh,
        "grant_type": "refresh_token",
    }).encode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if post_json is None:
        payload = _post_form(TOKEN_URI, body, headers)
    else:
        payload = post_json(TOKEN_URI, body, headers)
    access = payload.get("access_token")
    if not isinstance(access, str) or not access:
        raise DriveTokenError("Google did not return an access token")
    return {
        "access_token": access,
        "expires_in": int(payload.get("expires_in") or 0),
        "token_type": str(payload.get("token_type") or "Bearer"),
        "scope": payload.get("scope"),
    }


def _post_form(url: str, body: bytes, headers: dict[str, str]) -> dict[str, Any]:
    import json
    from urllib.request import Request, urlopen
    req = Request(url, data=body, headers=headers, method="POST")
    with urlopen(req, timeout=20) as resp:
        raw = json.loads(resp.read().decode())
    if not isinstance(raw, dict):
        raise DriveTokenError("Google token response was not an object")
    return raw
