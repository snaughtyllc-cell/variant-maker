"""Look-first visual gate: actual frames, not the VMAF proxy."""
from __future__ import annotations

import os
import subprocess
import time

import pytest
from conftest import HAS_FFMPEG

from variant_maker import look, uniqueness

pytestmark = pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")


def _clip(path: str, *, seconds: float = 1.0, w: int = 320, h: int = 560) -> str:
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", f"testsrc2=size={w}x{h}:rate=15:duration={seconds}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", path,
        ],
        check=True,
        capture_output=True,
    )
    return path


def _overlay_blotch(src: str, dest: str) -> str:
    """Gross luma lift in the lookaqmtp MAE band (real pack scored 41–57)."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", src,
            "-vf", "geq=lum='clip(lum(X,Y)+45,0,255)':cb='cb(X,Y)':cr='cr(X,Y)'",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", dest,
        ],
        check=True,
        capture_output=True,
    )
    return dest


def test_look_gate_is_tighter_than_lookaqmtp_shade():
    assert look.LOOK_LUMA_MAX == 38.0
    assert look.LOOK_GRID == (16, 28)
    assert look.LOOK_METRIC == "coarse_luma_v1"


def test_look_unknown_on_missing_file(tmp_path):
    out = look.score_look(str(tmp_path / "nope.mp4"), str(tmp_path / "also.mp4"))
    assert out["look_status"] == "unknown"
    assert out["look_mae"] is None


def test_identity_look_ok(tmp_path):
    src = _clip(str(tmp_path / "src.mp4"))
    scored = look.score_look(src, src)
    assert scored["look_status"] == look.STATUS_NO_ALARM
    assert scored["look_mae"] == 0
    assert scored["look_mae_max"] == 0
    assert scored["look_frames"]
    assert scored["look_artifact_sha256"]


def test_gross_luma_blotch_fails_look(tmp_path):
    src = _clip(str(tmp_path / "src.mp4"))
    blotch = _overlay_blotch(src, str(tmp_path / "blotch.mp4"))
    scored = look.score_look(src, blotch)
    assert scored["look_status"] == look.STATUS_REVIEW_REQUIRED
    assert scored["look_mae_max"] > look.LOOK_LUMA_MAX


def test_reencode_without_shade_passes_look(tmp_path):
    src = _clip(str(tmp_path / "src.mp4"))
    dest = str(tmp_path / "clean.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", src,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", dest,
        ],
        check=True,
        capture_output=True,
    )
    scored = look.score_look(src, dest)
    assert scored["look_status"] == look.STATUS_NO_ALARM
    assert scored["look_mae_max"] <= look.LOOK_LUMA_MAX


def test_lookaqmtp_real_pack_fails_look():
    """Lab lava pack vs source. Skip when the local clips are not on disk."""
    src = "/tmp/vf-screen-unique/03_ig720_aqmtp_th.mp4"
    lava = "/tmp/vf-lab8/aqmtp4540720/03_ig720_aqmtp_th_v01_f75d6cca.mp4"
    medium = "/tmp/vf-first-pass/03_ig720_aqmtp_th_first.mp4"
    if not all(os.path.isfile(p) for p in (src, lava, medium)):
        pytest.skip("lookaqmtp clips not on this machine")
    assert look.score_look(src, lava)["look_status"] == look.STATUS_REVIEW_REQUIRED
    assert look.score_look(src, medium)["look_status"] == look.STATUS_NO_ALARM


def test_stills_and_mae_are_not_the_uniqueness_wait(tmp_path):
    """Side-channel stills + coarse MAE must finish inside the SSIM uniqueness budget.

    Overlap only keeps Generate wait flat if uniqueness is the slower of the two.
    """
    src = _clip(str(tmp_path / "src.mp4"), seconds=1.5, w=640, h=1120)
    dest = str(tmp_path / "v.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", src,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", dest,
        ],
        check=True,
        capture_output=True,
    )
    t0 = time.perf_counter()
    look.write_look_stills(src, dest, str(tmp_path), 1)
    stills_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    look.score_look(src, dest)
    mae_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    uniqueness.score_uniqueness(src, dest, target=uniqueness.DEFAULT_TARGET)
    uniq_s = time.perf_counter() - t0
    # SSIM extracts 6 frames + 3 SSIM pairs. Stills are 2 JPEGs; MAE is 3 tiny blends.
    # Overlap wall is max(stills, MAE, uniqueness). Uniqueness must be that max.
    assert uniq_s >= stills_s
    assert uniq_s >= mae_s


def test_write_look_stills(tmp_path):
    src = _clip(str(tmp_path / "src.mp4"))
    names = look.write_look_stills(src, src, str(tmp_path), 1)
    assert names["look_src"] == "look_v01_src.jpg"
    assert names["look_var"] == "look_v01.jpg"
    assert os.path.getsize(tmp_path / names["look_src"]) > 0
    assert os.path.getsize(tmp_path / names["look_var"]) > 0
