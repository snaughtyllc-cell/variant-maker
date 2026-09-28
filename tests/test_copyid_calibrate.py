"""CopyID calibration: identity re-encode vs an unrelated pair.

Clip-agnostic. Do not pin these tests to old look-pack talking-head files —
those are not the clips getting flagged.
"""
from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from variant_maker.copyid.backends import FakeBackend
from variant_maker.copyid.calibrate import (
    COPY_BITS_CEIL,
    COPY_SIM_FLOOR,
    DISTINCT_BITS_FLOOR,
    DISTINCT_SIM_CEIL,
    MIN_BITS_GAP,
    MIN_SIM_GAP,
    PLATFORM_PROXY_SIZE,
    calibrate_paths,
    interpret_bits,
    interpret_sim,
    platform_proxy_canvas,
)
from variant_maker.uniqueness import TARGET_BITS, bits_vs


def test_gate_stays_twenty_four():
    """Calibration does not raise the SSIM gate. Duplicate/unoriginal is not a 24-bits miss."""
    assert TARGET_BITS == 24


def test_interpret_sim_separates_copy_from_unrelated():
    r = interpret_sim(0.99, 0.20)
    assert r["separates"] is True
    assert r["status"] == "separates"
    assert r["gap"] == pytest.approx(0.79)
    assert r["reencode"] == 0.99
    assert r["unrelated"] == 0.20


def test_midband_controls_are_collapsed():
    """0.74 vs 0.77 with no gap is not a uniqueness verdict — it is uncalibrated collapse."""
    r = interpret_sim(0.74, 0.77)
    assert r["separates"] is False
    assert r["status"] == "collapsed"
    assert r["gap"] < MIN_SIM_GAP


def test_interpret_sim_unknown_when_missing():
    r = interpret_sim(None, 0.2)
    assert r["available"] is False
    assert r["status"] == "unknown"
    assert r["separates"] is False


def test_interpret_sim_inverted():
    r = interpret_sim(0.20, 0.95)
    assert r["separates"] is False
    assert r["status"] == "inverted"


def test_interpret_sim_weak_when_reencode_below_floor_but_gap_holds():
    r = interpret_sim(0.80, 0.20)
    assert r["reencode"] < COPY_SIM_FLOOR
    assert r["unrelated"] <= DISTINCT_SIM_CEIL
    assert r["status"] == "weak"
    assert r["separates"] is False


def test_interpret_bits_separates():
    r = interpret_bits(2, 40)
    assert r["separates"] is True
    assert r["status"] == "separates"
    assert r["reencode"] == 2
    assert r["unrelated"] == 40
    assert r["gap"] == 38


def test_interpret_bits_collapsed_when_both_copy_like():
    r = interpret_bits(2, 5)
    assert r["separates"] is False
    assert r["status"] == "collapsed"
    assert r["gap"] < MIN_BITS_GAP


def test_platform_proxy_is_even_224():
    assert PLATFORM_PROXY_SIZE == 224
    assert platform_proxy_canvas() == (224, 224)
    assert platform_proxy_canvas()[0] % 2 == 0
    assert COPY_SIM_FLOOR > DISTINCT_SIM_CEIL
    assert COPY_BITS_CEIL < DISTINCT_BITS_FLOOR
    assert DISTINCT_BITS_FLOOR == TARGET_BITS


def test_bits_vs_accepts_proxy_canvas(tmp_path):
    a = tmp_path / "a.mp4"
    b = tmp_path / "b.mp4"
    _lavfi(str(a), "color=c=black:s=320x180:d=1")
    _lavfi(str(b), "color=c=white:s=320x180:d=1")
    gate = bits_vs(str(a), str(b))
    proxy = bits_vs(str(a), str(b), canvas=platform_proxy_canvas())
    assert gate >= TARGET_BITS
    assert proxy >= TARGET_BITS


def test_fine_detail_collapses_at_224(tmp_path):
    """High-frequency grain/checkers that 576 SSIM can see should shrink at 224.

    Platform copy-id is closer to this downscale than to the uniqueness canvas.
    """
    clean = tmp_path / "clean.mp4"
    noisy = tmp_path / "noisy.mp4"
    _lavfi(str(clean), "color=c=gray:s=640x360:d=1", qp0=True)
    _lavfi(
        str(noisy),
        "color=c=gray:s=640x360:d=1",
        vf="noise=alls=80:allf=u",
        qp0=True,
    )
    gate_bits = bits_vs(str(clean), str(noisy))
    proxy_bits = bits_vs(str(clean), str(noisy), canvas=platform_proxy_canvas())
    assert gate_bits > proxy_bits
    assert proxy_bits < gate_bits


def test_calibrate_paths_ssim_generic_reencode_vs_unrelated(tmp_path):
    src = tmp_path / "src.mp4"
    reenc = tmp_path / "reenc.mp4"
    unrel = tmp_path / "unrel.mp4"
    _lavfi(str(src), "testsrc=size=320x180:rate=25:duration=1")
    _reencode(str(src), str(reenc))
    _lavfi(str(unrel), "color=c=red:s=320x180:d=1")
    report = calibrate_paths(str(src), str(reenc), str(unrel), audio=False)
    assert report["ssim"]["separates"] is True
    assert report["ssim"]["reencode"] <= COPY_BITS_CEIL
    assert report["ssim"]["unrelated"] >= DISTINCT_BITS_FLOOR
    assert report["audio"]["status"] == "skipped"
    assert report["visual"]["status"] == "skipped"


def test_calibrate_paths_audio_injected(tmp_path):
    src = tmp_path / "src.mp4"
    reenc = tmp_path / "reenc.mp4"
    unrel = tmp_path / "unrel.mp4"
    src.write_bytes(b"x")
    reenc.write_bytes(b"y")
    unrel.write_bytes(b"z")

    def score_audio_fn(a, b, **_kw):
        if "unrel" in os.path.basename(b):
            return {"available": True, "sim": 0.18, "uniqueness": 0.82, "status": "ok"}
        return {"available": True, "sim": 0.97, "uniqueness": 0.03, "status": "ok"}

    report = calibrate_paths(
        str(src), str(reenc), str(unrel),
        audio=True, score_audio_fn=score_audio_fn, score_ssim=False,
    )
    assert report["audio"]["separates"] is True
    assert report["audio"]["status"] == "separates"
    assert report["ssim"]["status"] == "skipped"


def test_calibrate_paths_visual_fake_backend():
    backend = FakeBackend(encode_fn=_encode_by_stem)
    report = calibrate_paths(
        "src.mp4", "reenc.mp4", "unrel.mp4",
        audio=False, score_ssim=False,
        visual_backend=backend,
        extract_fn=lambda path, n=8, **k: [f"{path}-{i}" for i in range(2)],
    )
    assert report["visual"]["separates"] is True
    assert report["visual"]["reencode"] > COPY_SIM_FLOOR
    assert report["visual"]["unrelated"] < DISTINCT_SIM_CEIL


def test_calibrate_paths_separates_if_any_head_does(tmp_path):
    src = tmp_path / "src.mp4"
    reenc = tmp_path / "reenc.mp4"
    unrel = tmp_path / "unrel.mp4"
    _lavfi(str(src), "testsrc=size=160x90:rate=25:duration=1")
    _reencode(str(src), str(reenc))
    _lavfi(str(unrel), "color=c=blue:s=160x90:d=1")
    report = calibrate_paths(str(src), str(reenc), str(unrel), audio=False)
    assert report["separates"] is True


@pytest.mark.skipif(not shutil.which("fpcalc"), reason="fpcalc not on PATH")
def test_calibrate_paths_chromaprint_tone_vs_other_tone(tmp_path):
    src = tmp_path / "src.mp4"
    reenc = tmp_path / "reenc.mp4"
    unrel = tmp_path / "unrel.mp4"
    _tone(str(src), freq=440)
    _reencode(str(src), str(reenc), audio=True)
    _tone(str(unrel), freq=880)
    report = calibrate_paths(str(src), str(reenc), str(unrel), audio=True)
    assert report["audio"]["available"] is True
    assert report["audio"]["reencode"] > report["audio"]["unrelated"]


def _encode_by_stem(paths):
    tag = paths[0]
    if "unrel" in tag:
        return [[0.0, 1.0], [0.0, 1.0]]
    return [[1.0, 0.0], [1.0, 0.0]]


def _lavfi(path: str, lavfi: str, *, vf: str | None = None, qp0: bool = False) -> None:
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", lavfi]
    if vf:
        cmd += ["-vf", vf]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "1"]
    if qp0:
        cmd += ["-preset", "ultrafast", "-qp", "0"]
    cmd += [path]
    subprocess.run(cmd, check=True, capture_output=True)


def _reencode(src: str, dest: str, *, audio: bool = False) -> None:
    cmd = [
        "ffmpeg", "-y", "-i", src,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
    ]
    if audio:
        cmd += ["-c:a", "aac"]
    else:
        cmd += ["-an"]
    cmd += [dest]
    subprocess.run(cmd, check=True, capture_output=True)


def _tone(path: str, *, freq: int) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1",
            "-f", "lavfi", "-i", f"sine=frequency={freq}:duration=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", path,
        ],
        check=True,
        capture_output=True,
    )

