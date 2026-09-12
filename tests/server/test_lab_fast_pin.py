"""Lab Studio boot may pin Lab Fast. Never Live."""
from __future__ import annotations

import json

import pytest

from variant_maker.server.lab_fast_pin import (
    DEFAULT_IMAGE,
    LAB_FAST_ENDPOINT,
    LIVE_FAST_ENDPOINT,
    pin_lab_fast_endpoint,
    resolve_lab_image,
    sanitize_detail,
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
    from variant_maker.server import lab_fast_pin as mod
    assert mod.LAST_STATUS == "pinned"
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
    live_pinned = []
    monkeypatch.setattr(
        "variant_maker.server.lab_fast_pin.pin_lab_fast_endpoint",
        lambda environ=None: pinned.append(True) or "pinned",
    )
    monkeypatch.setattr(
        "variant_maker.server.live_fast_pin.pin_live_fast_endpoint",
        lambda environ=None: live_pinned.append(True) or "pinned",
    )
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: None)
    monkeypatch.setattr("sys.argv", ["variant-server", "--data-dir", str(tmp_path)])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    assert pinned == [True]
    assert live_pinned == [True]


def test_sanitize_detail_strips_live_id_and_keys():
    raw = (
        f"PATCH live {LIVE_FAST_ENDPOINT} Bearer secret-token "
        "https://api.runpod.io/graphql?api_key=secret-token"
    )
    out = sanitize_detail(raw, ["secret-token"])
    assert LIVE_FAST_ENDPOINT not in out
    assert "secret-token" not in out
    assert "[live]" in out
    assert "[redacted]" in out


def test_resolve_lab_image_uses_digest_not_mutable_tag():
    digest = "sha256:" + "ab" * 32
    image = resolve_lab_image(
        {"VARIANT_LAB": "1"},
        resolve_digest=lambda: digest,
    )
    assert image.endswith("@" + digest)
    assert ":lab" not in image.split("@")[-1]
    assert LIVE_FAST_ENDPOINT not in image


def test_v2_403_falls_back_to_v1_endpoint_patch():
    calls = []

    def http(method, url, key, body=None, **kw):
        calls.append((method, url, body))
        assert LIVE_FAST_ENDPOINT not in url
        if "api.runpod.io/v2/serverless" in url:
            return 403, '{"error":"forbidden"}'
        if method == "PATCH" and "rest.runpod.io/v1/endpoints/" in url:
            assert body == {
                "imageName": "ghcr.io/snaughtyllc-cell/variant-fast@sha256:" + "cd" * 32
            }
            return 200, '{"id":"xar25v77v3j27u"}'
        return 500, "unexpected"

    digest = "sha256:" + "cd" * 32
    status = pin_lab_fast_endpoint(
        {
            "VARIANT_LAB": "1",
            "RUNPOD_API_KEY": "job-key",
            "RUNPOD_FAST_ENDPOINT_ID": LAB_FAST_ENDPOINT,
        },
        http=http,
        resolve_digest=lambda: digest,
    )
    assert status == "pinned"
    assert any("rest.runpod.io/v1/endpoints/" + LAB_FAST_ENDPOINT in u for _, u, _ in calls)
    assert all(LIVE_FAST_ENDPOINT not in u for _, u, _ in calls)
    from variant_maker.server import lab_fast_pin as mod
    assert "job-key" not in mod.LAST_DETAIL
    assert LIVE_FAST_ENDPOINT not in mod.LAST_DETAIL


def test_shared_template_is_never_patched():
    calls = []

    def http(method, url, key, body=None, **kw):
        calls.append((method, url))
        assert LIVE_FAST_ENDPOINT not in url
        if "/templates/" in url:
            raise AssertionError("must not patch a template Live also uses")
        if "graphql" in url:
            return 200, json.dumps({
                "data": {
                    "myself": {
                        "endpoints": [
                            {"id": LAB_FAST_ENDPOINT, "templateId": "sharedtpl"},
                            {"id": LIVE_FAST_ENDPOINT, "templateId": "sharedtpl"},
                        ]
                    }
                }
            })
        return 403, '{"error":"forbidden"}'

    status = pin_lab_fast_endpoint(
        {
            "VARIANT_LAB": "1",
            "RUNPOD_API_KEY": "k",
            "RUNPOD_FAST_ENDPOINT_ID": LAB_FAST_ENDPOINT,
        },
        http=http,
        resolve_digest=lambda: "sha256:" + "ee" * 32,
    )
    assert status.startswith("error_")
    assert all("/templates/" not in u for _, u in calls)


def test_lab_only_template_is_patched_after_v2_403():
    calls = []

    def http(method, url, key, body=None, **kw):
        calls.append((method, url, body))
        assert LIVE_FAST_ENDPOINT not in url
        if "api.runpod.io/v2/serverless" in url:
            return 403, "no"
        if method == "PATCH" and "rest.runpod.io/v1/endpoints/" in url:
            return 400, '{"error":"no imageName"}'
        if method == "POST" and url.endswith("/update"):
            return 400, "no"
        if "graphql" in url and body and body.get("query", "").startswith("query"):
            return 200, json.dumps({
                "data": {
                    "myself": {
                        "endpoints": [
                            {"id": LAB_FAST_ENDPOINT, "templateId": "labtpl"},
                        ]
                    }
                }
            })
        if method == "PATCH" and url.endswith("/templates/labtpl"):
            assert body == {"imageName": DEFAULT_IMAGE}
            return 200, '{"id":"labtpl"}'
        return 403, "no"

    status = pin_lab_fast_endpoint(
        {
            "VARIANT_LAB": "1",
            "RUNPOD_API_KEY": "k",
            "RUNPOD_FAST_ENDPOINT_ID": LAB_FAST_ENDPOINT,
        },
        http=http,
    )
    assert status == "pinned"
    assert any(
        method == "PATCH" and url.endswith("/templates/labtpl")
        for method, url, _ in calls
    )


def test_prefers_endpoint_update_key_over_job_key():
    keys_seen = []

    def http(method, url, key, body=None, **kw):
        keys_seen.append(key)
        return 200, "ok"

    status = pin_lab_fast_endpoint(
        {
            "VARIANT_LAB": "1",
            "RUNPOD_API_KEY": "job-only",
            "RUNPOD_ENDPOINT_UPDATE_KEY": "mgmt-write",
            "RUNPOD_FAST_ENDPOINT_ID": LAB_FAST_ENDPOINT,
        },
        http=http,
    )
    assert status == "pinned"
    assert keys_seen[0] == "mgmt-write"


def test_update_key_alone_is_enough():
    calls = []
    status = pin_lab_fast_endpoint(
        {
            "VARIANT_LAB": "1",
            "RUNPOD_ENDPOINT_UPDATE_KEY": "mgmt",
            "RUNPOD_FAST_ENDPOINT_ID": LAB_FAST_ENDPOINT,
        },
        http=lambda method, url, key, body=None, **kw: calls.append(key) or (200, "ok"),
    )
    assert status == "pinned"
    assert calls == ["mgmt"]


def test_graphql_save_template_when_rest_write_is_403():
    calls = []

    def http(method, url, key, body=None, **kw):
        calls.append((method, url, body, kw.get("graphql_query_key")))
        assert LIVE_FAST_ENDPOINT not in url
        if "graphql" in url:
            query = (body or {}).get("query", "")
            if query.startswith("query"):
                assert kw.get("graphql_query_key") is True
                return 200, json.dumps({
                    "data": {
                        "myself": {
                            "endpoints": [
                                {"id": LAB_FAST_ENDPOINT, "templateId": "labtpl"},
                            ]
                        }
                    }
                })
            assert "saveTemplate" in query
            variables = (body or {}).get("variables") or {}
            assert variables.get("id") == "labtpl"
            assert LIVE_FAST_ENDPOINT not in json.dumps(body)
            return 200, json.dumps({
                "data": {"saveTemplate": {"id": "labtpl", "imageName": "x"}}
            })
        return 403, '{"error":"forbidden"}'

    status = pin_lab_fast_endpoint(
        {
            "VARIANT_LAB": "1",
            "RUNPOD_API_KEY": "job-key",
            "RUNPOD_FAST_ENDPOINT_ID": LAB_FAST_ENDPOINT,
        },
        http=http,
    )
    assert status == "pinned"
    assert any(
        body and "saveTemplate" in (body.get("query") or "")
        for _, _, body, _ in calls
    )
    from variant_maker.server import lab_fast_pin as mod
    assert "job-key" not in mod.LAST_DETAIL
    assert LIVE_FAST_ENDPOINT not in mod.LAST_DETAIL
