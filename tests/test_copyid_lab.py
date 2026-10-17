"""Lab-only: real SSCD / fpcalc. Skip unless COPYID_LAB=1."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

import pytest

pytestmark = pytest.mark.lab

LAB = os.environ.get("COPYID_LAB") == "1" or os.environ.get("VARIANT_MAKER_COPYID_LAB") == "1"


def _skip_unless_lab():
    if not LAB:
        pytest.skip("set COPYID_LAB=1 on the lab box")


def _clip(path, *, lavfi, has_audio=False):
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", lavfi]
    if has_audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-shortest"]
        cmd += ["-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "1", path]
    subprocess.run(cmd, check=True, capture_output=True)


@pytest.mark.skipif(not shutil.which("fpcalc"), reason="fpcalc missing")
def test_lab_chromaprint_same_tone_high_sim():
    _skip_unless_lab()
    from variant_maker.copyid.chromaprint import score_audio

    with tempfile.TemporaryDirectory() as d:
        a = os.path.join(d, "a.mp4")
        b = os.path.join(d, "b.mp4")
        _clip(a, lavfi="color=c=black:s=64x64:d=1", has_audio=True)
        _clip(b, lavfi="color=c=black:s=64x64:d=1", has_audio=True)
        r = score_audio(a, b)
        assert r["available"] is True
        assert r["sim"] is not None and r["sim"] > 0.8


def test_lab_sscd_identical_frames_high_sim():
    _skip_unless_lab()
    from variant_maker.copyid.backends import score_visual
    from variant_maker.copyid.sscd import SscdBackend

    backend = SscdBackend()
    if not backend.available():
        pytest.skip("SSCD weights or torch missing")
    with tempfile.TemporaryDirectory() as d:
        a = os.path.join(d, "a.mp4")
        b = os.path.join(d, "b.mp4")
        _clip(a, lavfi="testsrc=size=320x240:rate=8:duration=1")
        _clip(b, lavfi="testsrc=size=320x240:rate=8:duration=1")
        r = score_visual(a, b, backend, n_frames=4)
        assert r["available"] is True
        assert r["sim"] is not None and r["sim"] > 0.7
