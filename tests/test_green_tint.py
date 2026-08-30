"""Green/olive cast: compete vignette + ffmpeg eq saturation.

Jeff 2026-08-30: every NEW clip (source vs variant) had a green tint. Not
chroma-cloud (1080 talking-head draws full-res grain, not the 720 overlay).
The compare slider plays the actual mp4s. Root cause:

1. Vignette mapped to ffmpeg's default PI/5 (~0.63) minus a hair. That
   default crushes a 9:16 talking-head by ~40 RGB and reads olive on white
   walls. Sampled 0.02–0.20 is already a mild angle if passed through.
2. ffmpeg `eq=saturation=` converts YUV→RGB with a 601-ish matrix, then
   back, tagged bt709. Any sat ≠ 1 pushes G up / R+B down. `hue=s=` does not.
"""
from __future__ import annotations

import subprocess

import pytest
from conftest import HAS_FFMPEG

from variant_maker import filtergraph
from variant_maker.platforms import get_platform
from variant_maker.probe import ColorTags, SourceInfo

pytestmark = pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")

RGB_709 = (
    "zscale=matrixin=709:transferin=709:primariesin=709:rangein=limited:"
    "matrix=709:transfer=iec61966-2-1:primaries=bt709:range=full,format=rgb24"
)


def _mean_rgb(path: str, vf: str, t: float = 0.0) -> tuple[float, float, float]:
    cmd = [
        "ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", path,
        "-frames:v", "1", "-vf", vf, "-f", "rawvideo", "pipe:1",
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True)
    buf = proc.stdout
    n = len(buf) // 3
    if n <= 0:
        raise AssertionError(f"empty rgb from {path}")
    r = g = b = 0
    for i in range(0, len(buf), 3):
        r += buf[i]
        g += buf[i + 1]
        b += buf[i + 2]
    return r / n, g / n, b / n


def _encode_bt709(path: str, lavfi: str) -> str:
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", lavfi,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
            "-colorspace", "bt709", "-color_primaries", "bt709",
            "-color_trc", "bt709", "-color_range", "tv", path,
        ],
        check=True, capture_output=True,
    )
    return path


def test_old_vignette_formula_would_crush_portrait():
    """Guard: do not map sampled vig through PI/5. That is the green-tint crush."""
    import math
    old = max(0.22, math.pi / 5.0 - 0.08)
    assert old > 0.50
    assert filtergraph.vignette_angle(0.08) < 0.30


@pytest.mark.integration
def test_medium_vignette_does_not_crush_portrait_gray(tmp_path):
    src = _encode_bt709(
        str(tmp_path / "gray.mp4"),
        "color=c=0xC8C4BE:size=1080x1920:rate=8:duration=0.5",
    )
    base = _mean_rgb(src, RGB_709)
    mild = _mean_rgb(src, f"vignette=angle={filtergraph.vignette_angle(0.08):.4f},{RGB_709}")
    drop = tuple(m - b for m, b in zip(mild, base))
    # Edge fingerprint only — not the ~50-point crush of angle=PI/5.
    assert all(d > -8.0 for d in drop), f"vignette crushed gray: {drop}"
    old = _mean_rgb(src, "vignette=angle=0.6072," + RGB_709)
    old_drop = tuple(m - b for m, b in zip(old, base))
    assert min(old_drop) < -20.0  # the bug we are not shipping


@pytest.mark.integration
def test_hue_saturation_does_not_push_green_on_gray(tmp_path):
    """Neutral field: eq sat ≠ 1 drops R+B and leaves G (olive). hue=s= is a no-op."""
    src = _encode_bt709(
        str(tmp_path / "gray.mp4"),
        "color=c=0x808080:size=1080x1920:rate=8:duration=0.5",
    )
    base = _mean_rgb(src, RGB_709)
    eq = _mean_rgb(src, "eq=saturation=0.9600," + RGB_709)
    hue = _mean_rgb(src, "hue=s=0.9600," + RGB_709)
    eq_green = (eq[1] - eq[0]) - (base[1] - base[0])
    hue_green = (hue[1] - hue[0]) - (base[1] - base[0])
    assert eq_green > 1.0, f"eq sat should be the olive path, got {eq_green}"
    assert abs(hue_green) < 0.5, f"hue=s= pushed green: {hue_green}"


@pytest.mark.integration
def test_filtergraph_color_stage_is_not_olive(tmp_path):
    src_path = _encode_bt709(
        str(tmp_path / "wall.mp4"),
        "color=c=0xC8C4BE:size=1080x1920:rate=8:duration=0.5",
    )
    src = SourceInfo(
        src_path, "x", 0.5, 1080, 1920, 8.0, False,
        ColorTags("tv", "bt709", "bt709", "bt709"),
    )
    params = {
        "video": {
            "crop_keep": 1.0, "crop_x_frac": 0.5, "crop_y_frac": 0.5,
            "rotate_deg": 0.0, "brightness": 0.0, "contrast": 1.0,
            "saturation": 0.96, "gamma": 1.0, "hue_deg": 0.0, "grain": 0.0,
            "unsharp": 0.0, "speed": 1.0, "trim_s": 0.0, "trim_end_s": 0.0,
            "crf": 18, "gop": 30, "vignette": 0.08,
        },
        "audio": {
            "speed": 1.0, "loudnorm_i": None, "eq_bands": 0, "eq_gains": [],
            "pitch_pct": 0.0, "aac_kbps": 128,
        },
    }
    vf = filtergraph.build_video_filters(params, src, get_platform("none"))
    assert "saturation=1.0000" in vf
    assert "hue=s=0.9600" in vf
    assert "vignette=angle=0.0800" in vf
    base = _mean_rgb(src_path, RGB_709)
    out = _mean_rgb(src_path, f"{vf},{RGB_709}")
    d_gr = (out[1] - out[0]) - (base[1] - base[0])
    luma_drop = (out[0] + out[1] + out[2]) / 3 - (base[0] + base[1] + base[2]) / 3
    assert d_gr < 1.5, f"filtergraph olive G-R {d_gr} rgb {base} -> {out}"
    assert luma_drop > -10.0, f"filtergraph crushed luma {luma_drop}"
