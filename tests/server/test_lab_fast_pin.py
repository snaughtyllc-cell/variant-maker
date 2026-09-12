"""Lab Studio boot may pin Lab Fast. Never Live."""
from __future__ import annotations

import pytest

from variant_maker.server.lab_fast_pin import (
    DEFAULT_IMAGE,
    LAB_FAST_ENDPOINT,
    LIVE_FAST_ENDPOINT,
    pin_lab_fast_endpoint,
    target_endpoint,
)


def test_skips_when_not_lab_mode():
    calls = []
    status = pin_lab_fast_endpoint(
        {
            "VARIANT_LAB": "",
            "RUNPOD_API_KEY": "k",
            "RUNPOD_FAST_ENDPOINT_ID": LAB_FAST_ENDPOINT,
        },
        patch=lambda *a: calls.append(a) or (200, "ok"),
    )
    assert status == "skipped_not_lab"
    assert calls == []


def test_skips_when_fast_endpoint_is_live():
    calls = []
    status = pin_lab_fast_endpoint(
        {
            "VARIANT_LAB": "1",
            "RUNPOD_API_KEY": "k",
            "RUNPOD_FAST_ENDPOINT_ID": LIVE_FAST_ENDPOINT,
        },
        patch=lambda *a: calls.append(a) or (200, "ok"),
    )
    assert status == "skipped_not_lab_endpoint"
    assert calls == []
    assert target_endpoint({"VARIANT_LAB": "1", "RUNPOD_FAST_ENDPOINT_ID": LIVE_FAST_ENDPOINT}) is None


def test_pins_lab_endpoint_never_live_url():
    calls = []
    status = pin_lab_fast_endpoint(
        {
            "VARIANT_LAB": "true",
            "RUNPOD_API_KEY": "secret",
            "RUNPOD_FAST_ENDPOINT_ID": LAB_FAST_ENDPOINT,
        },
        patch=lambda url, key, image: calls.append((url, key, image)) or (200, "ok"),
    )
    assert status == "pinned"
    assert len(calls) == 1
    url, key, image = calls[0]
    assert LAB_FAST_ENDPOINT in url
    assert LIVE_FAST_ENDPOINT not in url
    assert key == "secret"
    assert image == DEFAULT_IMAGE


def test_prefers_explicit_lab_fast_id_when_primary_is_live():
    calls = []
    status = pin_lab_fast_endpoint(
        {
            "VARIANT_LAB": "1",
            "RUNPOD_API_KEY": "k",
            "RUNPOD_FAST_ENDPOINT_ID": LIVE_FAST_ENDPOINT,
            "RUNPOD_FAST_LAB_ENDPOINT_ID": LAB_FAST_ENDPOINT,
        },
        patch=lambda url, key, image: calls.append(url) or (200, "ok"),
    )
    assert status == "pinned"
    assert LAB_FAST_ENDPOINT in calls[0]
    assert LIVE_FAST_ENDPOINT not in calls[0]


def test_skips_without_api_key():
    calls = []
    status = pin_lab_fast_endpoint(
        {
            "VARIANT_LAB": "1",
            "RUNPOD_FAST_ENDPOINT_ID": LAB_FAST_ENDPOINT,
        },
        patch=lambda *a: calls.append(a) or (200, "ok"),
    )
    assert status == "skipped_no_key"
    assert calls == []


def test_cli_main_pins_before_serving(tmp_path, monkeypatch):
    import uvicorn

    from variant_maker.server import cli

    pinned = []
    monkeypatch.setattr(
        "variant_maker.server.lab_fast_pin.pin_lab_fast_endpoint",
        lambda environ=None: pinned.append(True) or "pinned",
    )
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: None)
    monkeypatch.setattr("sys.argv", ["variant-server", "--data-dir", str(tmp_path)])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    assert pinned == [True]
