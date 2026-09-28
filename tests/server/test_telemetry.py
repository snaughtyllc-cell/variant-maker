"""Sentry / PostHog stay silent without keys and never raise into callers."""
from __future__ import annotations

import json

from variant_maker.server import telemetry


def test_capture_event_is_noop_without_keys(monkeypatch):
    monkeypatch.delenv("POSTHOG_KEY", raising=False)
    monkeypatch.delenv("POSTHOG_API_KEY", raising=False)
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    called = []
    monkeypatch.setattr(telemetry, "_post_json", lambda *a, **k: called.append((a, k)))
    telemetry.capture_event("job_completed", {"job_id": "j1"})
    assert called == []


def test_capture_event_posts_to_posthog(monkeypatch):
    monkeypatch.setenv("POSTHOG_KEY", "phc_test")
    monkeypatch.setenv("POSTHOG_HOST", "https://ph.example")
    posted = []

    def fake_post(url, payload, timeout=2.0):
        posted.append((url, payload, timeout))

    monkeypatch.setattr(telemetry, "_post_json", fake_post)
    telemetry.capture_event(
        "job_completed",
        {"job_id": "j1", "prep_mode": "hq", "fast_copies": 4},
        distinct_id="ws_lab",
    )
    assert len(posted) == 1
    url, payload, _ = posted[0]
    assert url == "https://ph.example/capture/"
    assert payload["api_key"] == "phc_test"
    assert payload["event"] == "job_completed"
    assert payload["distinct_id"] == "ws_lab"
    assert payload["properties"]["job_id"] == "j1"
    assert payload["properties"]["prep_mode"] == "hq"
    json.dumps(payload)  # must be JSON-safe


def test_capture_exception_swallows_posthog_errors(monkeypatch):
    monkeypatch.setenv("POSTHOG_KEY", "phc_test")

    def boom(*_a, **_k):
        raise OSError("offline")

    monkeypatch.setattr(telemetry, "_post_json", boom)
    telemetry.capture_exception(RuntimeError("gpu down"))
    telemetry.capture_event("job_completed", {})


def test_init_is_noop_without_sentry(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    telemetry.init()
