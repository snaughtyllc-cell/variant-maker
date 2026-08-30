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


def test_score_audio_prefers_ffmpeg_wav(monkeypatch, tmp_path):
    """Always decode with our ffmpeg first. Direct fpcalc on BtbN mp4s is the miss."""
    a = tmp_path / "a.mp4"
    b = tmp_path / "b.mp4"
    a.write_bytes(b"x")
    b.write_bytes(b"y")
    fp = [0xAAAAAAAA, 0x55555555, 0xFFFFFFFF, 0x0, 0x1, 0x2, 0x3, 0x4]
    monkeypatch.setattr("variant_maker.copyid.chromaprint.available", lambda: True)
    calls: list[str] = []

    def boom(path, *, length=120):
        calls.append("direct")
        raise subprocess.CalledProcessError(1, ["fpcalc"], stderr="decode")

    def wav(path, *, length=120):
        calls.append("wav")
        return fp

    monkeypatch.setattr("variant_maker.copyid.chromaprint._fpcalc_direct", boom)
    monkeypatch.setattr("variant_maker.copyid.chromaprint._fpcalc_via_ffmpeg", wav)
    r = score_audio(str(a), str(b))
    assert r["available"] is True
    assert r["via"] == "ffmpeg_wav"
    assert "wav" in calls
    assert "direct" not in calls


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


def test_score_audio_empty_direct_uses_wav(monkeypatch, tmp_path):
    a = tmp_path / "a.mp4"
    b = tmp_path / "b.mp4"
    a.write_bytes(b"x")
    b.write_bytes(b"y")
    fp = [0xAAAAAAAA, 0x55555555, 0xFFFFFFFF, 0x0, 0x1, 0x2, 0x3, 0x4]
    monkeypatch.setattr("variant_maker.copyid.chromaprint.available", lambda: True)
    monkeypatch.setattr(
        "variant_maker.copyid.chromaprint._fpcalc_direct",
        lambda path, *, length=120: [],
    )
    monkeypatch.setattr(
        "variant_maker.copyid.chromaprint._fpcalc_via_ffmpeg",
        lambda path, *, length=120: fp,
    )
    r = score_audio(str(a), str(b))
    assert r["available"] is True
    assert r["via"] == "ffmpeg_wav"


@pytest.mark.skipif(not shutil.which("fpcalc"), reason="fpcalc not on PATH")
def test_fpcalc_binary_reports_available():
    assert available() is True


@pytest.mark.skipif(
    not shutil.which("fpcalc") or not shutil.which("ffmpeg"),
    reason="fpcalc+ffmpeg needed",
)
def test_score_audio_on_aac_mp4(tmp_path):
    """Our encodes are BtbN libx264+aac. wav-first must score those, not error."""
    from conftest import HAS_FFMPEG
    if not HAS_FFMPEG:
        pytest.skip("needs ffmpeg")
    def tone(path):
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
                "-f", "lavfi", "-i", "color=c=black:s=64x64:r=15:d=6",
                "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "96k", path,
            ],
            check=True, capture_output=True,
        )
    a = str(tmp_path / "a.mp4")
    b = str(tmp_path / "b.mp4")
    tone(a)
    tone(b)
    r = score_audio(a, b)
    assert r["available"] is True, r
    assert r["sim"] is not None and r["sim"] > 0.9
    assert r["via"] == "ffmpeg_wav"


def test_score_audio_short_file_is_empty_not_error(monkeypatch, tmp_path):
    """fpcalc exits 2 with 'Empty fingerprint' on a 2s tone. That is a miss, not error."""
    a = tmp_path / "a.mp4"
    b = tmp_path / "b.mp4"
    a.write_bytes(b"x")
    b.write_bytes(b"y")
    monkeypatch.setattr("variant_maker.copyid.chromaprint.available", lambda: True)
    monkeypatch.setattr(
        "variant_maker.copyid.chromaprint._fpcalc_via_ffmpeg",
        lambda path, *, length=120: [],
    )
    monkeypatch.setattr(
        "variant_maker.copyid.chromaprint._fpcalc_direct",
        lambda path, *, length=120: [],
    )
    r = score_audio(str(a), str(b))
    assert r["available"] is False
    assert r["reason"] == "empty"
