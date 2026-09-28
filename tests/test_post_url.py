"""Pure post-link normalize — VAs paste a live permalink; Studio does not fetch it."""
from __future__ import annotations

import pytest

from variant_maker.server.post_url import MAX_POST_URL_LEN, normalize_post_url


def test_blank_clears():
    assert normalize_post_url(None) is None
    assert normalize_post_url("") is None
    assert normalize_post_url("   ") is None


def test_https_instagram_and_tiktok_kept():
    ig = "https://www.instagram.com/reel/AbC123/?igsh=xyz"
    assert normalize_post_url(ig) == ig
    tt = "https://www.tiktok.com/@someone/video/1234567890"
    assert normalize_post_url(tt) == tt


def test_scheme_less_gets_https():
    assert normalize_post_url("instagram.com/p/AbC/") == "https://instagram.com/p/AbC/"


def test_rejects_non_http_schemes():
    with pytest.raises(ValueError, match="https"):
        normalize_post_url("javascript:alert(1)")
    with pytest.raises(ValueError, match="https"):
        normalize_post_url("data:text/html,hi")
    with pytest.raises(ValueError, match="https"):
        normalize_post_url("file:///etc/passwd")


def test_rejects_no_host():
    with pytest.raises(ValueError, match="link"):
        normalize_post_url("https://")
    with pytest.raises(ValueError, match="link"):
        normalize_post_url("not a url")


def test_rejects_too_long():
    with pytest.raises(ValueError, match="long"):
        normalize_post_url("https://instagram.com/" + ("a" * MAX_POST_URL_LEN))


def test_strips_whitespace_and_fragment():
    assert (
        normalize_post_url("  https://youtube.com/shorts/xyz#t=3  ")
        == "https://youtube.com/shorts/xyz"
    )
