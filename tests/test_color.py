import subprocess

import pytest

from variant_maker import color
from variant_maker.probe import ColorTags
from conftest import HAS_FFMPEG, mean_saturation


def test_resolve_carries_source():
    src = ColorTags("pc", "bt709", "bt709", "bt709")
    assert color.resolve_output_color(src).range == "pc"


def test_resolve_defaults_unknowns_to_hd():
    out = color.resolve_output_color(ColorTags(None, None, None, None))
    assert out == color.BT709


def test_output_args_tag_everything():
    args = color.output_color_args(color.BT709)
    for flag in ("-colorspace", "-color_primaries", "-color_trc", "-color_range"):
        assert flag in args


def test_needs_conversion_detects_range_diff():
    assert color.needs_conversion(ColorTags("pc", None, None, None), color.BT709) is True
    assert color.needs_conversion(ColorTags(None, None, None, None), color.BT709) is False


def test_even_scale_forces_even():
    assert "trunc(iw/2)*2" in color.even_scale_filter(1080, 1920)


@pytest.mark.integration
@pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")
def test_saturation_roundtrip_preserved(sample_clip, tmp_path):
    """THE wash-out guard: a correctly-tagged re-encode must preserve saturation.

    This is the Phase-2 acceptance check. If color tags/range were dropped, SATAVG
    would collapse and this fails — exactly the '1990s phone' symptom.
    """
    out = str(tmp_path / "reencoded.mp4")
    out_color = color.resolve_output_color(ColorTags("tv", "bt709", "bt709", "bt709"))
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-i", sample_clip,
        "-vf", color.even_scale_filter(640, 360),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-map_metadata", "-1",
        *color.output_color_args(out_color),
        out,
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    src_sat = mean_saturation(sample_clip)
    out_sat = mean_saturation(out)
    # within 8% — no systematic desaturation
    assert abs(out_sat - src_sat) / src_sat < 0.08, f"src={src_sat:.1f} out={out_sat:.1f}"
