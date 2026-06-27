import subprocess

import pytest

from variant_maker import quality, ffmpeg
from variant_maker.probe import probe
from variant_maker.platforms import get_platform
from conftest import HAS_FFMPEG

NONE = get_platform("none")
REELS = get_platform("reels")


def _neutral_params():
    return {
        "video": {
            "crop_keep": 1.0, "rotate_deg": 0.0, "brightness": 0.0, "contrast": 1.0,
            "saturation": 1.0, "gamma": 1.0, "hue_deg": 0.0, "grain": 0.0, "unsharp": 0.0,
            "speed": 1.0, "trim_s": 0.0, "crf": 20, "gop": 60,
        },
        "audio": {"speed": 1.0, "loudnorm_i": -14.0, "eq_bands": 1, "eq_gains": [0.0],
                  "pitch_pct": 0.0, "aac_kbps": 160},
    }


@pytest.mark.integration
@pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")
def test_histogram_sanity_passes_clean_reencode(real_clip, tmp_path):
    """A correctly-tagged, color-neutral re-encode keeps luma+saturation -> passes."""
    src = probe(real_clip)
    out = str(tmp_path / "clean.mp4")
    ffmpeg.render_variant(src, _neutral_params(), NONE, out)
    assert quality.histogram_sanity(real_clip, out) is True


@pytest.mark.integration
@pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")
def test_signalstats_handles_special_char_paths(real_clip, tmp_path):
    """Real filenames have commas/quotes/spaces; lavfi movie= must not break on them."""
    import shutil
    weird = str(tmp_path / "a,b'c d.mp4")
    shutil.copy(real_clip, weird)
    assert quality.histogram_sanity(weird, weird) is True  # identical file -> identical stats


@pytest.mark.integration
@pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")
def test_histogram_sanity_fails_washed_out(real_clip, tmp_path):
    """The wash-out symptom: saturation collapses -> guard rejects it."""
    out = str(tmp_path / "washed.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", real_clip,
         "-vf", "eq=saturation=0.3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-an", out],
        check=True, capture_output=True,
    )
    assert quality.histogram_sanity(real_clip, out) is False


@pytest.mark.integration
@pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")
def test_quality_render_matches_source_geometry(real_clip, tmp_path):
    """The quality proxy strips geometric/temporal ops so VMAF can frame-align it to source."""
    src = probe(real_clip)
    qr = quality.quality_render(src, _neutral_params(), str(tmp_path / "qr.mp4"))
    info = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", qr],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert info == f"{src.width},{src.height}"


@pytest.mark.integration
@pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")
def test_vmaf_high_for_clean_quality_render(real_clip, tmp_path):
    src = probe(real_clip)
    qr = quality.quality_render(src, _neutral_params(), str(tmp_path / "clean.mp4"))
    assert quality.vmaf(real_clip, qr) > 85


@pytest.mark.integration
@pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")
def test_vmaf_drops_for_degraded_render(real_clip, tmp_path):
    src = probe(real_clip)
    clean = quality.quality_render(src, _neutral_params(), str(tmp_path / "clean.mp4"))
    bad_params = _neutral_params()
    bad_params["video"].update({"crf": 51, "grain": 40.0})
    bad = quality.quality_render(src, bad_params, str(tmp_path / "bad.mp4"))
    assert quality.vmaf(real_clip, bad) < quality.vmaf(real_clip, clean) - 10


# ---- regen loop (pure: reject -> reduce strength -> regenerate) -------------

def test_regen_loop_reduces_strength_until_pass():
    seen = []

    def attempt(strength):
        seen.append(strength)
        return {"passed": strength <= 0.4, "vmaf": 100 * strength, "histogram_ok": True}

    res = quality.regen_until_pass(attempt, max_regen=3, strength=1.0, falloff=0.6)
    assert res["passed"] is True
    assert res["regen_count"] == 2
    assert seen == [1.0, pytest.approx(0.6), pytest.approx(0.36)]


def test_regen_loop_bounded_by_max_regen():
    calls = {"n": 0}

    def attempt(strength):
        calls["n"] += 1
        return {"passed": False, "vmaf": 10.0, "histogram_ok": False}

    res = quality.regen_until_pass(attempt, max_regen=2, strength=1.0)
    assert res["passed"] is False
    assert res["regen_count"] == 2
    assert calls["n"] == 3  # initial attempt + 2 regenerations


# ---- combined guard decision (integration) ----------------------------------

@pytest.mark.integration
@pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")
def test_passes_guard_accepts_clean_variant(real_clip, tmp_path):
    src = probe(real_clip)
    variant, _ = ffmpeg.render_variant(src, _neutral_params(), REELS, str(tmp_path / "v.mp4"))
    qr = quality.quality_render(src, _neutral_params(), str(tmp_path / "qr.mp4"))
    r = quality.passes_guard(real_clip, variant, qr)
    assert r["passed"] is True and r["vmaf"] > 90 and r["histogram_ok"] is True


@pytest.mark.integration
@pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")
def test_passes_guard_rejects_degraded_variant(real_clip, tmp_path):
    src = probe(real_clip)
    bad = _neutral_params()
    bad["video"].update({"crf": 51, "grain": 40.0})
    variant, _ = ffmpeg.render_variant(src, bad, REELS, str(tmp_path / "v.mp4"))
    qr = quality.quality_render(src, bad, str(tmp_path / "qr.mp4"))
    assert quality.passes_guard(real_clip, variant, qr)["passed"] is False
