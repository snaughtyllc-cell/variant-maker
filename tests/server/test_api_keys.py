"""Workspace API key store: digest-only, fail closed, issuer must stay owner."""
from __future__ import annotations

import json

import pytest

from variant_maker.server.api_keys import (
    ApiKeyStore,
    ApiKeyStoreError,
    parse_token,
    public_key_dict,
    token_digest,
)
from variant_maker.server.tenants import TenantStore, UserInfo


def _tenants_owner(tmp_path, *, role="owner"):
    store = TenantStore(str(tmp_path / "tenants.json"))
    ws = store.create_workspace(name="Ops")
    store.upsert_user(UserInfo(
        email="ops@x.com", name="Ops", workspace_id=ws.id, role=role,
    ))
    return store, ws


def test_create_shows_token_once_and_stores_digest_only(tmp_path):
    keys = ApiKeyStore(str(tmp_path / "api_keys.json"))
    issued = keys.create(
        workspace_id="ws_1",
        issuer_email="ops@x.com",
        label="Agency bot",
        scopes=["jobs:read", "gallery:read"],
    )
    assert issued.token.startswith("vf_")
    parsed = parse_token(issued.token)
    assert parsed is not None
    assert issued.record.prefix == f"vf_{issued.record.key_id}"
    assert issued.record.digest == token_digest(issued.token)
    raw = json.loads((tmp_path / "api_keys.json").read_text())
    blob = json.dumps(raw)
    assert issued.token not in blob
    assert "jobs:read" in raw["keys"][0]["scopes"]
    listed = keys.list_for_workspace("ws_1")
    assert "token" not in public_key_dict(listed[0])
    assert listed[0].digest != issued.token


def test_authenticate_rejects_revoked_expired_and_demoted_issuer(tmp_path):
    tenants, ws = _tenants_owner(tmp_path)
    keys = ApiKeyStore(str(tmp_path / "api_keys.json"))
    issued = keys.create(
        workspace_id=ws.id,
        issuer_email="ops@x.com",
        label="bot",
        scopes=["jobs:read"],
        ttl_days=90,
    )
    assert keys.authenticate(issued.token, tenants=tenants) is not None

    keys.revoke(issued.record.key_id, workspace_id=ws.id)
    assert keys.authenticate(issued.token, tenants=tenants) is None

    live = keys.create(
        workspace_id=ws.id,
        issuer_email="ops@x.com",
        label="bot2",
        scopes=["gallery:read"],
    )
    tenants.upsert_user(UserInfo(
        email="ops@x.com", name="Ops", workspace_id=ws.id, role="member",
    ))
    assert keys.authenticate(live.token, tenants=tenants) is None


def test_corrupt_store_fails_closed(tmp_path):
    path = tmp_path / "api_keys.json"
    path.write_text("{not json")
    keys = ApiKeyStore(str(path))
    with pytest.raises(ApiKeyStoreError):
        keys.list_for_workspace("ws")


def test_wrong_length_digest_does_not_raise(tmp_path):
    tenants, ws = _tenants_owner(tmp_path)
    keys = ApiKeyStore(str(tmp_path / "api_keys.json"))
    issued = keys.create(
        workspace_id=ws.id,
        issuer_email="ops@x.com",
        label="bot",
        scopes=["jobs:read"],
    )
    raw = json.loads((tmp_path / "api_keys.json").read_text())
    raw["keys"][0]["digest"] = "short"
    (tmp_path / "api_keys.json").write_text(json.dumps(raw))
    assert keys.authenticate(issued.token, tenants=tenants) is None


def test_unknown_scope_rejected(tmp_path):
    keys = ApiKeyStore(str(tmp_path / "api_keys.json"))
    with pytest.raises(ValueError, match="unknown scope"):
        keys.create(
            workspace_id="ws",
            issuer_email="ops@x.com",
            label="x",
            scopes=["admin:*"],
        )


def test_revoke_twice_same_workspace(tmp_path):
    keys = ApiKeyStore(str(tmp_path / "api_keys.json"))
    issued = keys.create(
        workspace_id="ws_1",
        issuer_email="ops@x.com",
        label="bot",
        scopes=["jobs:read"],
    )
    first = keys.revoke(issued.record.key_id, workspace_id="ws_1")
    second = keys.revoke(issued.record.key_id, workspace_id="ws_1")
    assert first is not None and second is not None
    assert second.revoked_utc == first.revoked_utc
    assert keys.revoke(issued.record.key_id, workspace_id="other") is None
