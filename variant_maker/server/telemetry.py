"""Env-gated Sentry + PostHog. No keys → no-op. Never raise into the job loop."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

POSTHOG_KEY_ENVS = ("POSTHOG_KEY", "POSTHOG_API_KEY")
SENTRY_DSN_ENV = "SENTRY_DSN"
DEFAULT_POSTHOG_HOST = "https://us.i.posthog.com"


def _posthog_key() -> str:
    for name in POSTHOG_KEY_ENVS:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def _posthog_host() -> str:
    return (os.environ.get("POSTHOG_HOST") or DEFAULT_POSTHOG_HOST).rstrip("/")


def _post_json(url: str, payload: dict[str, Any], timeout: float = 2.0) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return


def init() -> None:
    dsn = (os.environ.get(SENTRY_DSN_ENV) or "").strip()
    if not dsn:
        return
    try:
        import sentry_sdk
    except ImportError:
        return
    try:
        sentry_sdk.init(dsn=dsn, traces_sample_rate=0.0, send_default_pii=False)
    except Exception:  # noqa: BLE001 — optional SDK must never fail Studio boot
        return


def capture_event(
    name: str,
    properties: dict[str, Any] | None = None,
    *,
    distinct_id: str = "studio",
) -> None:
    key = _posthog_key()
    if not key:
        return
    props = dict(properties or {})
    props.setdefault("$lib", "variant-maker")
    try:
        _post_json(
            f"{_posthog_host()}/capture/",
            {
                "api_key": key,
                "event": name,
                "distinct_id": distinct_id,
                "properties": props,
            },
        )
    except Exception:  # noqa: BLE001 — telemetry must never fail a job
        return


def capture_exception(exc: BaseException) -> None:
    try:
        import sentry_sdk
    except ImportError:
        sentry_sdk = None
    if sentry_sdk is not None:
        try:
            sentry_sdk.capture_exception(exc)
        except Exception:  # noqa: BLE001, S110 — optional SDK
            pass
    if _posthog_key():
        capture_event(
            "$exception",
            {"error_type": type(exc).__name__, "error": str(exc)[:400]},
        )
