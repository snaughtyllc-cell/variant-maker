import json
from variant_maker.server import drive_config as dc


def test_not_configured_when_env_unset(monkeypatch):
    monkeypatch.delenv(dc.ENV_SA_JSON, raising=False)
    info = dc.resolve_drive_status(environ={})
    assert info.status == "not_configured"
    assert info.sa_email is None
    assert "VARIANT_DRIVE_SERVICE_ACCOUNT_JSON" in info.message


def test_ready_reads_client_email(tmp_path, monkeypatch):
    p = tmp_path / "sa.json"
    p.write_text(json.dumps({"client_email": "bot@project.iam.gserviceaccount.com"}))
    monkeypatch.setenv(dc.ENV_SA_JSON, str(p))
    info = dc.resolve_drive_status()
    assert info.status == "ready"
    assert info.sa_email == "bot@project.iam.gserviceaccount.com"


def test_auth_failed_missing_file(tmp_path):
    info = dc.resolve_drive_status(str(tmp_path / "missing.json"))
    assert info.status == "auth_failed"
    assert "missing.json" in info.message or "unreadable" in info.message.lower()


def test_auth_failed_invalid_json(tmp_path):
    p = tmp_path / "sa.json"
    p.write_text("{not-json")
    info = dc.resolve_drive_status(str(p))
    assert info.status == "auth_failed"


def test_share_email_defaults(monkeypatch):
    monkeypatch.delenv(dc.ENV_SHARE_EMAIL, raising=False)
    assert dc.read_share_email({}) == ""


def test_share_email_from_env():
    assert dc.read_share_email({dc.ENV_SHARE_EMAIL: " ops@varyforge.app "}) == "ops@varyforge.app"


def test_effective_share_email_stays_on_connected_gmail_until_override():
    info = dc.DriveConfigInfo(
        "ready", None, "Drive ready (Google OAuth)",
        auth_mode="oauth",
        connected_email="snaughtyllc@gmail.com",
        oauth_available=True,
    )
    assert dc.effective_share_email(info, {}) == "snaughtyllc@gmail.com"
    assert dc.effective_share_email(
        info, {dc.ENV_SHARE_EMAIL: "drive@varyforge.app"},
    ) == "drive@varyforge.app"
