import os
import subprocess
import tempfile

from variant_maker import uniqueness


def _tiny_mp4(path, *, color="black", extra_vf=None, lavfi=None):
    # 1s clip via lavfi (solid color or custom source)
    src = lavfi or f"color=c={color}:s=64x64:d=1"
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", src]
    if extra_vf:
        cmd += ["-vf", extra_vf]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "1", path]
    subprocess.run(cmd, check=True, capture_output=True)


def test_bits_from_ssim_math():
    assert uniqueness.bits_from_ssim(1.0) == 0
    assert uniqueness.bits_from_ssim(0.0) == 64
    # TikFusion floor ≈ 18 bits. Fast vs-source gate is 24 (medium 20-pack headroom).
    # Local uniqueness only — not a platform verdict.
    assert uniqueness.bits_from_ssim(1.0 - 18 / 64) == 18
    assert uniqueness.bits_from_ssim(1.0 - uniqueness.TARGET_BITS / 64) == uniqueness.TARGET_BITS
    assert uniqueness.TARGET_BITS == 24
    assert uniqueness.DEFAULT_TARGET == uniqueness.TARGET_BITS / 64
    # Sibling floor matches vs-source: 24 bits so a Fast 20-pack stays on medium.
    assert uniqueness.MIN_PEER_BITS == 24
    assert uniqueness.DEFAULT_PEER == uniqueness.MIN_PEER_BITS
    assert uniqueness.MAX_PASSES == 3


def test_fast_gate_fits_medium_talking_head_headroom():
    """Pass stays 24 bits (~38% UI). 1080 medium talking-head can land ~35–42 bits.

    Raising the *gate* to 32 previously escalated entire Fast 20-packs. 720 Fast
    with usable chroma lands ~26–31 bits (~40–48%) — still a pass. Delivery is
    not Pixel AI scramble and not a higher floor.
    """
    talking_head_medium_typical = 35
    assert uniqueness.TARGET_BITS == 24
    assert uniqueness.TARGET_BITS < talking_head_medium_typical


def test_similarity_is_one_minus_uniqueness():
    assert uniqueness.similarity_from_uniqueness(uniqueness.DEFAULT_TARGET) == 1.0 - uniqueness.DEFAULT_TARGET
    assert uniqueness.similarity_from_uniqueness(0.0) == 1.0
    assert uniqueness.similarity_from_uniqueness(1.0) == 0.0


def test_identical_videos_low_bits_below_target():
    with tempfile.TemporaryDirectory() as d:
        a = os.path.join(d, "a.mp4")
        b = os.path.join(d, "b.mp4")
        _tiny_mp4(a)
        _tiny_mp4(b)
        r = uniqueness.score_uniqueness(a, b, target=uniqueness.DEFAULT_TARGET)
        assert r["uniqueness_metric"] == "ssim_bits_v1"
        assert r["bits"] is not None and r["bits"] < 8
        assert r["uniqueness"] is not None and r["uniqueness"] < uniqueness.DEFAULT_TARGET
        assert r["uniqueness_status"] == "below_target"
        assert r["uniqueness_target"] == uniqueness.DEFAULT_TARGET


def test_different_colors_higher_bits():
    with tempfile.TemporaryDirectory() as d:
        a = os.path.join(d, "a.mp4")
        b = os.path.join(d, "b.mp4")
        _tiny_mp4(a, color="black")
        _tiny_mp4(b, color="white")
        r = uniqueness.score_uniqueness(a, b, target=uniqueness.DEFAULT_TARGET)
        assert r["uniqueness_metric"] == "ssim_bits_v1"
        assert r["bits"] is not None and r["bits"] >= uniqueness.TARGET_BITS
        assert r["uniqueness"] >= uniqueness.DEFAULT_TARGET
        assert r["uniqueness_status"] == "ok"


def test_transformed_clip_scores_higher_than_identical():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "src.mp4")
        twin = os.path.join(d, "twin.mp4")
        crop = os.path.join(d, "crop.mp4")
        # Patterned source so a spatial crop actually changes SSIM (solid gray would not).
        pattern = "testsrc=size=128x128:rate=25:duration=1"
        _tiny_mp4(src, lavfi=pattern)
        _tiny_mp4(twin, lavfi=pattern)
        _tiny_mp4(crop, lavfi=pattern, extra_vf="crop=96:96:16:16,scale=128:128")
        identical = uniqueness.score_uniqueness(src, twin)
        transformed = uniqueness.score_uniqueness(src, crop)
        assert identical["bits"] is not None and transformed["bits"] is not None
        assert transformed["bits"] > identical["bits"]


def test_bits_vs_helper():
    with tempfile.TemporaryDirectory() as d:
        a = os.path.join(d, "a.mp4")
        b = os.path.join(d, "b.mp4")
        _tiny_mp4(a, color="black")
        _tiny_mp4(b, color="white")
        assert uniqueness.bits_vs(a, b) >= uniqueness.TARGET_BITS


def test_missing_file_unknown():
    r = uniqueness.score_uniqueness("/nope/a.mp4", "/nope/b.mp4")
    assert r["uniqueness"] is None and r["uniqueness_status"] == "unknown"
    assert r["uniqueness_metric"] == "ssim_bits_v1"
    assert r["bits"] is None


def test_invalid_probe_duration_unknown(monkeypatch):
    def fake_probe(_path):
        raise ValueError("no valid duration in ffprobe output: 'N/A'")

    monkeypatch.setattr(uniqueness, "_probe_duration", fake_probe)
    with tempfile.TemporaryDirectory() as d:
        a = os.path.join(d, "a.mp4")
        _tiny_mp4(a)
        r = uniqueness.score_uniqueness(a, a)
    assert r["uniqueness"] is None and r["uniqueness_status"] == "unknown"
