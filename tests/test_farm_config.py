"""Farm config: global defaults + per-client overrides, validated, fail-fast."""
import pytest

from variant_maker.farm import config as cfg


def _raw(**ov):
    base = {
        "auth": {"service_account_json": "./secrets/variant-bot.json"},
        "defaults": {"preset": "medium", "count": 10, "platform": "reels", "quality": "fast"},
        "poll_minutes": 15,
        "clients": {
            "logan": {"input_folder_id": "IN1", "output_folder_id": "OUT1"},
        },
    }
    base.update(ov)
    return base


def test_client_inherits_defaults_when_no_overrides():
    c = cfg.from_dict(_raw())
    logan = c.clients["logan"]
    assert logan.recipe.preset == "medium"
    assert logan.recipe.count == 10
    assert logan.recipe.platform == "reels"
    assert logan.recipe.quality == "fast"
    assert logan.input_folder_id == "IN1"
    assert logan.output_folder_id == "OUT1"


def test_per_client_override_wins_over_defaults():
    raw = _raw(clients={
        "logan": {"input_folder_id": "IN1", "output_folder_id": "OUT1",
                  "preset": "strong", "count": 20},
    })
    logan = cfg.from_dict(raw).clients["logan"]
    assert logan.recipe.preset == "strong"   # override
    assert logan.recipe.count == 20          # override
    assert logan.recipe.platform == "reels"  # inherited
    assert logan.recipe.quality == "fast"    # inherited


def test_auth_and_poll_minutes_parsed():
    c = cfg.from_dict(_raw())
    assert c.auth.service_account_json == "./secrets/variant-bot.json"
    assert c.poll_minutes == 15


def test_poll_minutes_defaults_to_15_when_absent():
    raw = _raw()
    del raw["poll_minutes"]
    assert cfg.from_dict(raw).poll_minutes == 15


def test_missing_input_folder_id_raises():
    raw = _raw(clients={"logan": {"output_folder_id": "OUT1"}})
    with pytest.raises(cfg.ConfigError, match="input_folder_id"):
        cfg.from_dict(raw)


def test_missing_output_folder_id_raises():
    raw = _raw(clients={"logan": {"input_folder_id": "IN1"}})
    with pytest.raises(cfg.ConfigError, match="output_folder_id"):
        cfg.from_dict(raw)


def test_same_input_and_output_folder_id_raises():
    raw = _raw(clients={"logan": {"input_folder_id": "SAME", "output_folder_id": "SAME"}})
    with pytest.raises(cfg.ConfigError, match="different"):
        cfg.from_dict(raw)


def test_missing_auth_raises():
    raw = _raw()
    del raw["auth"]
    with pytest.raises(cfg.ConfigError, match="auth"):
        cfg.from_dict(raw)


def test_oauth_token_auth_accepted():
    raw = _raw(auth={"oauth_token": "./token.json"})
    c = cfg.from_dict(raw)
    assert c.auth.oauth_token == "./token.json"
    assert c.auth.service_account_json is None


def test_service_account_auth_still_accepted():
    c = cfg.from_dict(_raw())
    assert c.auth.service_account_json == "./secrets/variant-bot.json"
    assert c.auth.oauth_token is None


def test_both_auth_methods_is_an_error():
    raw = _raw(auth={"service_account_json": "a.json", "oauth_token": "b.json"})
    with pytest.raises(cfg.ConfigError, match="exactly one|both"):
        cfg.from_dict(raw)


def test_no_auth_method_is_an_error():
    raw = _raw(auth={})
    with pytest.raises(cfg.ConfigError, match="service_account_json|oauth_token"):
        cfg.from_dict(raw)


def test_no_clients_raises():
    raw = _raw(clients={})
    with pytest.raises(cfg.ConfigError, match="client"):
        cfg.from_dict(raw)


def test_unknown_preset_fails_fast():
    raw = _raw(defaults={"preset": "wobbly", "count": 10, "platform": "reels", "quality": "fast"})
    with pytest.raises(cfg.ConfigError, match="preset"):
        cfg.from_dict(raw)


def test_unknown_platform_fails_fast():
    raw = _raw(clients={
        "logan": {"input_folder_id": "IN1", "output_folder_id": "OUT1", "platform": "myspace"},
    })
    with pytest.raises(cfg.ConfigError, match="platform"):
        cfg.from_dict(raw)


def test_unknown_quality_fails_fast():
    raw = _raw(clients={
        "logan": {"input_folder_id": "IN1", "output_folder_id": "OUT1", "quality": "ultra"},
    })
    with pytest.raises(cfg.ConfigError, match="quality"):
        cfg.from_dict(raw)


def test_load_reads_yaml_file(tmp_path):
    yaml = pytest.importorskip("yaml")
    p = tmp_path / "farm.yaml"
    p.write_text(yaml.safe_dump(_raw()))
    c = cfg.load(str(p))
    assert c.clients["logan"].input_folder_id == "IN1"
    assert c.poll_minutes == 15
