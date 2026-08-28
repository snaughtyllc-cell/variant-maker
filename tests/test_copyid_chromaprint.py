import shutil

import pytest

from variant_maker.copyid.chromaprint import (
    AUDIO_METRIC,
    available,
    match_fingerprints,
    parse_raw,
    score_audio,
)


def test_parse_raw_comma_and_spaces():
    text = "FILE=a.mp4\nDURATION=12\nFINGERPRINT=1,2,3,4\n"
    assert parse_raw(text) == [1, 2, 3, 4]
    text2 = "FINGERPRINT=10 20 30"
    assert parse_raw(text2) == [10, 20, 30]


def test_parse_raw_missing_raises():
    try:
        parse_raw("DURATION=1\n")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_identical_fingerprints_match():
    a = [0xAAAAAAAA, 0x55555555, 0xFFFFFFFF, 0x0, 0x1, 0x2, 0x3, 0x4]
    assert match_fingerprints(a, a) == 1.0


def test_offset_shift_still_matches():
    a = [10, 20, 30, 40, 50, 60, 70, 80, 90]
    b = [0, 0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
    assert match_fingerprints(a, b) > 0.99


def test_flipped_bits_lower_score():
    a = [0] * 16
    b = [0xFFFFFFFF] * 16
    assert match_fingerprints(a, b) == 0.0


def test_score_audio_unavailable_without_fpcalc(monkeypatch):
    monkeypatch.setattr("variant_maker.copyid.chromaprint.available", lambda: False)
    r = score_audio("/nope/a.mp4", "/nope/b.mp4")
    assert r["available"] is False
    assert r["uniqueness"] is None
    assert r["metric"] == AUDIO_METRIC


@pytest.mark.skipif(not shutil.which("fpcalc"), reason="fpcalc not on PATH")
def test_fpcalc_binary_reports_available():
    assert available() is True
