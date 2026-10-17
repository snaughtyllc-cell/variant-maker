import shutil
import subprocess

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
    assert r["reason"] == "no_fpcalc"


def test_score_audio_reason_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr("variant_maker.copyid.chromaprint.available", lambda: True)
    r = score_audio(str(tmp_path / "a.mp4"), str(tmp_path / "b.mp4"))
    assert r["available"] is False
    assert r["reason"] == "missing_file"


def test_score_audio_falls_back_to_ffmpeg_wav(monkeypatch, tmp_path):
    """Slim Fast fpcalc's libav often cannot decode our BtbN mp4s."""
    a = tmp_path / "a.mp4"
    b = tmp_path / "b.mp4"
    a.write_bytes(b"x")
    b.write_bytes(b"y")
    fp = [0xAAAAAAAA, 0x55555555, 0xFFFFFFFF, 0x0, 0x1, 0x2, 0x3, 0x4]
    monkeypatch.setattr("variant_maker.copyid.chromaprint.available", lambda: True)

    def boom(path, *, length=120):
        raise subprocess.CalledProcessError(1, ["fpcalc"], stderr="decode")

    monkeypatch.setattr("variant_maker.copyid.chromaprint._fpcalc_direct", boom)
    monkeypatch.setattr(
        "variant_maker.copyid.chromaprint._fpcalc_via_ffmpeg",
        lambda path, *, length=120: fp,
    )
    r = score_audio(str(a), str(b))
    assert r["available"] is True
    assert r["sim"] == 1.0
    assert r["via"] == "ffmpeg_wav"


def test_score_audio_reason_error_when_both_paths_fail(monkeypatch, tmp_path):
    a = tmp_path / "a.mp4"
    b = tmp_path / "b.mp4"
    a.write_bytes(b"x")
    b.write_bytes(b"y")
    monkeypatch.setattr("variant_maker.copyid.chromaprint.available", lambda: True)

    def boom(path, *, length=120):
        raise subprocess.CalledProcessError(1, ["fpcalc"], stderr="nope")

    monkeypatch.setattr("variant_maker.copyid.chromaprint._fpcalc_direct", boom)
    monkeypatch.setattr("variant_maker.copyid.chromaprint._fpcalc_via_ffmpeg", boom)
    r = score_audio(str(a), str(b))
    assert r["available"] is False
    assert r["reason"] == "error"


@pytest.mark.skipif(not shutil.which("fpcalc"), reason="fpcalc not on PATH")
def test_fpcalc_binary_reports_available():
    assert available() is True
