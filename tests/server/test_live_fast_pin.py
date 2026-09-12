"""Lab Studio boot may pin Live Fast image. Never env / VF_LAB / Lab URL."""
from __future__ import annotations

import pytest

from variant_maker.server.lab_fast_pin import LAB_FAST_ENDPOINT
from variant_maker.server.live_fast_pin import (
    LIVE_FAST_ENDPOINT,
    PINNED_IMAGE,
    pin_live_fast_endpoint,
    resolve_live_image,
    sanitize_detail,
    target_endpoint,
)


def test_skips_when_not_lab_mode():
    calls = []
    status = pin_live_fast_endpoint(
        {
            "VARIANT_LAB": "",
            "RUNPOD_API_KEY": "k",
            "RUNPOD_FAST_ENDPOINT_ID": LAB_FAST_ENDPOINT,
        },
        patch=lambda *a: calls.append(a) or (200, "ok"),
    )
    assert status == "skipped_not_lab"
    assert calls == []
    assert target_endpoint({"VARIANT_LAB": "", "RUNPOD_API_KEY": "k"}) is None


def test_skips_when_one_shot_disabled():
    calls = []
    status = pin_live_fast_endpoint(
        {
            "VARIANT_LAB": "1",
            "VARIANT_LIVE_FAST_PIN": "0",
            "RUNPOD_API_KEY": "k",
        },
        patch=lambda *a: calls.append(a) or (200, "ok"),
    )
    assert status == "skipped_disabled"
    assert calls == []


def test_skips_when_one_shot_spent():
    calls = []
    status = pin_live_fast_endpoint(
        {"VARIANT_LAB": "1", "RUNPOD_API_KEY": "k"},
        patch=lambda *a: calls.append(a) or (200, "ok"),
    )
    assert status == "skipped_disabled"
    assert calls == []


def test_skips_without_api_key():
    calls = []
    status = pin_live_fast_endpoint(
        {"VARIANT_LAB": "1", "VARIANT_LIVE_FAST_PIN": "1"},
        patch=lambda *a: calls.append(a) or (200, "ok"),
    )
    assert status == "skipped_no_key"
    assert calls == []


def test_pins_live_url_never_lab_url():
    calls = []
    status = pin_live_fast_endpoint(
        {
            "VARIANT_LAB": "true",
            "VARIANT_LIVE_FAST_PIN": "1",
            "RUNPOD_API_KEY": "secret",
            "RUNPOD_FAST_ENDPOINT_ID": LAB_FAST_ENDPOINT,
        },
        patch=lambda url, key, image: calls.append((url, key, image)) or (200, "ok"),
    )
    assert status == "pinned"
    from variant_maker.server import live_fast_pin as mod

    assert mod.LAST_STATUS == "pinned"
    url, key, image = calls[0]
    assert LIVE_FAST_ENDPOINT in url
    assert LAB_FAST_ENDPOINT not in url
    assert key == "secret"
    assert image == PINNED_IMAGE
    assert "VF_LAB" not in image
    assert ":lab" not in image


def test_http_body_is_image_only_no_env():
    calls = []

    def http(method, url, key, body=None, **kw):
        calls.append((method, url, body))
        assert LAB_FAST_ENDPOINT not in url
        assert body == {"image": PINNED_IMAGE}
        assert "env" not in body
        assert "envVars" not in body
        assert "VF_LAB" not in str(body)
        return 200, "ok"

    status = pin_live_fast_endpoint(
        {"VARIANT_LAB": "1", "VARIANT_LIVE_FAST_PIN": "1", "RUNPOD_API_KEY": "k"},
        http=http,
    )
    assert status == "pinned"
    assert calls[0][0] == "PATCH"
    assert "v2/serverless/" + LIVE_FAST_ENDPOINT in calls[0][1]


def test_v2_403_falls_back_to_v1_image_name_only():
    calls = []

    def http(method, url, key, body=None, **kw):
        calls.append((method, url, body))
        assert LAB_FAST_ENDPOINT not in url
        if "api.runpod.io/v2/serverless" in url:
            return 403, '{"error":"forbidden"}'
        if method == "PATCH" and "rest.runpod.io/v1/endpoints/" in url:
            assert body == {"imageName": PINNED_IMAGE}
            assert "env" not in body
            assert "VF_LAB" not in str(body)
            return 200, '{"id":"j0b1q4iuunzhnq"}'
        raise AssertionError(f"unexpected {method} {url} {body}")

    status = pin_live_fast_endpoint(
        {"VARIANT_LAB": "1", "VARIANT_LIVE_FAST_PIN": "1", "RUNPOD_API_KEY": "job-key"},
        http=http,
    )
    assert status == "pinned"
    assert any("rest.runpod.io/v1/endpoints/" + LIVE_FAST_ENDPOINT in u for _, u, _ in calls)
    assert all(LAB_FAST_ENDPOINT not in u for _, u, _ in calls)
    from variant_maker.server import live_fast_pin as mod

    assert "job-key" not in mod.LAST_DETAIL
    assert "VF_LAB" not in mod.LAST_DETAIL
    assert "env" not in (mod.LAST_DETAIL or "")


def test_does_not_patch_templates():
    calls = []

    def http(method, url, key, body=None, **kw):
        calls.append((method, url, body))
        if "/templates/" in url or "graphql" in url:
            raise AssertionError("live pin must not touch templates")
        return 403, '{"error":"forbidden"}'

    status = pin_live_fast_endpoint(
        {"VARIANT_LAB": "1", "VARIANT_LIVE_FAST_PIN": "1", "RUNPOD_API_KEY": "k"},
        http=http,
    )
    assert status.startswith("error_")
    assert all("/templates/" not in u and "graphql" not in u for _, u, _ in calls)


def test_refuses_image_override_with_vf_lab_or_lab_id():
    calls = []
    status = pin_live_fast_endpoint(
        {
            "VARIANT_LAB": "1",
            "VARIANT_LIVE_FAST_PIN": "1",
            "RUNPOD_API_KEY": "k",
            "VARIANT_LIVE_FAST_IMAGE": (
                f"ghcr.io/snaughtyllc-cell/variant-fast@sha256:{'ab' * 32}"
                f"?VF_LAB=1#{LAB_FAST_ENDPOINT}"
            ),
        },
        patch=lambda *a: calls.append(a) or (200, "ok"),
    )
    assert status == "skipped_bad_image"
    assert calls == []


def test_resolve_live_image_default_is_fc5a8109_digest():
    image = resolve_live_image({})
    assert image == PINNED_IMAGE
    assert image.endswith(
        "@sha256:fc5a81090bac281b33eae122c087b19d6c9f0c090f8a68a2c1a2686723866097"
    )
    assert "VF_LAB" not in image
    assert LAB_FAST_ENDPOINT not in image


def test_resolve_live_image_accepts_digest_override():
    digest = "sha256:" + "cd" * 32
    image = resolve_live_image(
        {"VARIANT_LIVE_FAST_IMAGE": f"ghcr.io/snaughtyllc-cell/variant-fast@{digest}"}
    )
    assert image.endswith("@" + digest)


def test_sanitize_detail_strips_keys_and_lab_id():
    raw = (
        f"PATCH lab {LAB_FAST_ENDPOINT} Bearer secret-token "
        "https://api.runpod.io/graphql?api_key=secret-token VF_LAB=1"
    )
    out = sanitize_detail(raw, ["secret-token"])
    assert LAB_FAST_ENDPOINT not in out
    assert "secret-token" not in out
    assert "[lab]" in out
    assert "[redacted]" in out


def test_prefers_endpoint_update_key():
    keys_seen = []

    def http(method, url, key, body=None, **kw):
        keys_seen.append(key)
        return 200, "ok"

    status = pin_live_fast_endpoint(
        {
            "VARIANT_LAB": "1",
            "VARIANT_LIVE_FAST_PIN": "1",
            "RUNPOD_API_KEY": "job-only",
            "RUNPOD_ENDPOINT_UPDATE_KEY": "mgmt-write",
        },
        http=http,
    )
    assert status == "pinned"
    assert keys_seen[0] == "mgmt-write"


def test_cli_main_pins_live_after_lab(tmp_path, monkeypatch):
    import uvicorn

    from variant_maker.server import cli

    order = []
    monkeypatch.setattr(
        "variant_maker.server.lab_fast_pin.pin_lab_fast_endpoint",
        lambda environ=None: order.append("lab") or "pinned",
    )
    monkeypatch.setattr(
        "variant_maker.server.live_fast_pin.pin_live_fast_endpoint",
        lambda environ=None: order.append("live") or "pinned",
    )
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: None)
    monkeypatch.setattr("sys.argv", ["variant-server", "--data-dir", str(tmp_path)])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    assert order == ["lab", "live"]
