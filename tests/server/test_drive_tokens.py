from variant_maker.server.drive_tokens import DriveTokenError, mint_access_token


def test_mint_access_token_never_returns_refresh_token():
    posted = []

    def fake_post(url, body, headers):
        posted.append((url, body, headers))
        return {
            "access_token": "ya29.job-scoped",
            "expires_in": 3600,
            "token_type": "Bearer",
            "refresh_token": "should-not-leak",
        }

    out = mint_access_token(
        {"refresh_token": "rt_secret", "token": "old"},
        client_id="cid",
        client_secret="csec",
        post_json=fake_post,
    )
    assert out["access_token"] == "ya29.job-scoped"
    assert "refresh_token" not in out
    assert b"rt_secret" in posted[0][1]
    assert b"grant_type=refresh_token" in posted[0][1]


def test_mint_access_token_uses_existing_access_when_no_refresh():
    out = mint_access_token(
        {"access_token": "ya29.already"},
        client_id="cid",
        client_secret="csec",
        post_json=lambda *_: {"access_token": "nope"},
    )
    assert out["access_token"] == "ya29.already"
    assert "refresh_token" not in out


def test_mint_access_token_requires_some_credential():
    try:
        mint_access_token({}, client_id="c", client_secret="s", post_json=lambda *_: {})
        raise AssertionError("expected DriveTokenError")
    except DriveTokenError:
        pass
