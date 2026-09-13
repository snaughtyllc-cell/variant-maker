"""HTTP client for the public Studio /api/v1 contract.

Runs on the agency machine. The key never leaves that process except as a
Bearer header. Cookie UI routes are not called.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

import httpx

PACK_COUNTS = frozenset({8, 20})


class StudioV1Error(RuntimeError):
    """Public API error. Message must never include the API key."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def validate_base_url(raw: str) -> str:
    url = (raw or "").strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("VARIMO_BASE_URL must be an http(s) origin")
    if parsed.username or parsed.password:
        raise ValueError("VARIMO_BASE_URL must not include credentials")
    if parsed.path not in ("", "/"):
        raise ValueError("VARIMO_BASE_URL must be the Studio origin")
    host = (parsed.hostname or "").lower()
    local = host in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme == "http" and not local:
        raise ValueError("VARIMO_BASE_URL must be https (localhost http is Lab only)")
    return f"{parsed.scheme}://{parsed.netloc}"


def _detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"Studio API {response.status_code}"
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, str) and detail.strip():
        return detail.strip()
    return f"Studio API {response.status_code}"


class StudioV1Client:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._base = validate_base_url(base_url)
        self._key = (api_key or "").strip()
        if not self._key:
            raise ValueError("VARIMO_API_KEY required")
        self._http = httpx.Client(
            base_url=self._base,
            transport=transport,
            follow_redirects=False,
            timeout=timeout,
        )

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> StudioV1Client:
        env = environ if environ is not None else os.environ
        return cls(
            base_url=str(env.get("VARIMO_BASE_URL") or ""),
            api_key=str(env.get("VARIMO_API_KEY") or ""),
        )

    def close(self) -> None:
        self._http.close()

    def create_pack(
        self,
        *,
        input_destination_id: str,
        drive_file_id: str,
        count: int,
        request_id: str,
    ) -> dict[str, Any]:
        if int(count) not in PACK_COUNTS:
            raise ValueError("count must be 8 or 20")
        key = (request_id or "").strip()
        if not key:
            raise ValueError("request_id required")
        return self._request(
            "POST",
            "/api/v1/packs",
            json={
                "input_destination_id": input_destination_id,
                "drive_file_id": drive_file_id,
                "count": int(count),
            },
            request_id=key,
        )

    def get_pack(self, pack_id: str) -> dict[str, Any]:
        pid = (pack_id or "").strip()
        if not pid:
            raise ValueError("pack_id required")
        return self._request("GET", f"/api/v1/packs/{pid}")

    def list_gallery(
        self,
        *,
        pack_id: str | None = None,
        limit: int = 25,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str | int] = {"limit": min(100, max(1, int(limit)))}
        if pack_id:
            params["pack_id"] = pack_id
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/api/v1/gallery", params=params)

    def create_export(
        self,
        *,
        destination_id: str,
        variants: list[dict[str, Any]],
        request_id: str,
    ) -> dict[str, Any]:
        key = (request_id or "").strip()
        if not key:
            raise ValueError("request_id required")
        return self._request(
            "POST",
            "/api/v1/drive/exports",
            json={"destination_id": destination_id, "variants": variants},
            request_id=key,
        )

    def get_export(self, export_id: str) -> dict[str, Any]:
        eid = (export_id or "").strip()
        if not eid:
            raise ValueError("export_id required")
        return self._request("GET", f"/api/v1/drive/exports/{eid}")

    def _headers(self, request_id: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._key}",
            "Accept": "application/json",
        }
        if request_id:
            headers["Idempotency-Key"] = request_id
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str | int] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        response = self._http.request(
            method,
            path,
            json=json,
            params=params,
            headers=self._headers(request_id),
        )
        if response.status_code in {301, 302, 303, 307, 308}:
            raise StudioV1Error("redirect refused", status_code=response.status_code)
        if response.status_code >= 400:
            raise StudioV1Error(_detail(response), status_code=response.status_code)
        payload = response.json()
        if not isinstance(payload, dict):
            raise StudioV1Error("unexpected Studio API body")
        return payload
