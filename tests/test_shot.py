"""Look-first shot probe: source self-similarity → talking_head vs motion."""
from __future__ import annotations

from variant_maker import shot
from variant_maker.uniqueness import TARGET_BITS


def test_classify_talking_head_when_source_frames_are_alike(monkeypatch, tmp_path):
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"fake")
    monkeypatch.setattr(shot, "_duration", lambda path, given=None: 4.0)
    monkeypatch.setattr(shot.uniqueness, "_extract_frame", lambda *a, **k: None)
    monkeypatch.setattr(shot.uniqueness, "_ssim_pair", lambda a, b: 0.80)  # ~13 bits
    out = shot.classify_shot(str(src), duration_s=4.0)
    assert out["kind"] == "talking_head"
    assert out["self_bits"] == 13
    assert out["self_bits"] < TARGET_BITS


def test_classify_motion_when_source_frames_already_differ(monkeypatch, tmp_path):
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"fake")
    monkeypatch.setattr(shot, "_duration", lambda path, given=None: 4.0)
    monkeypatch.setattr(shot.uniqueness, "_extract_frame", lambda *a, **k: None)
    monkeypatch.setattr(shot.uniqueness, "_ssim_pair", lambda a, b: 0.40)  # ~38 bits
    out = shot.classify_shot(str(src), duration_s=4.0)
    assert out["kind"] == "motion"
    assert out["self_bits"] == 38
    assert out["self_bits"] >= TARGET_BITS


def test_classify_missing_file_is_neutral():
    out = shot.classify_shot("no-such-clip.mp4")
    assert out["kind"] is None
    assert out["self_bits"] is None


def test_gate_stays_twenty_four():
    assert TARGET_BITS == 24
    assert shot.TALKING_HEAD_SELF_BITS == 24


def test_talking_head_grain_band_is_heavier_than_preset():
    from variant_maker.presets import MEDIUM, STRONG, SUBTLE

    med = shot.grain_range_for_shot(MEDIUM, "talking_head")
    assert med is not None
    assert (med.lo, med.hi) == (34, 42)
    strong = shot.grain_range_for_shot(STRONG, "talking_head")
    assert strong is not None
    assert (strong.lo, strong.hi) == (46, 58)
    subtle = shot.grain_range_for_shot(SUBTLE, "talking_head")
    assert subtle is not None
    assert (subtle.lo, subtle.hi) == (24, 36)
    assert shot.grain_range_for_shot(MEDIUM, "motion") is None
    assert shot.grain_range_for_shot(MEDIUM, None) is None


def test_talking_head_chroma_cloud_band_is_softer_than_six_ten():
    """Live SaveInta 6–10 + sigma=2 still read as chroma. Stay under 7; gate stays 24."""
    from variant_maker.presets import MEDIUM, STRONG

    r = shot.chroma_cloud_range_for_shot(MEDIUM, "talking_head")
    assert r is not None
    assert (r.lo, r.hi) == (4, 7)
    assert r.hi < 10
    assert shot.chroma_cloud_range_for_shot(MEDIUM, "motion") is None
    assert shot.chroma_cloud_range_for_shot(MEDIUM, None) is None
    # Strong 720 escalate pins the encode-surviving cap. Medium / 1080 stay 4–7.
    pinned = shot.chroma_cloud_range_for_shot(STRONG, "talking_head", 720, 1280)
    assert pinned is not None
    assert (pinned.lo, pinned.hi) == (7, 7)
    wide = shot.chroma_cloud_range_for_shot(STRONG, "talking_head", 1080, 1920)
    assert wide is not None
    assert (wide.lo, wide.hi) == (4, 7)


def test_talking_head_luma_dust_band_is_720_calibrated():
    """c0s=9 scored 23; 15–17 was a little much. Sit 11–13 to clear the 24 gate.

    Not stacked full-res chroma. 1080 talking-head stays 34–42 c1s. Gate stays 24.
    """
    from variant_maker.presets import MEDIUM, STRONG

    r = shot.luma_dust_range_for_shot(MEDIUM, "talking_head")
    assert r is not None
    assert (r.lo, r.hi) == (11, 13)
    assert r.lo > 9
    assert r.hi < 15
    assert shot.luma_dust_range_for_shot(MEDIUM, "motion") is None
    assert shot.luma_dust_range_for_shot(MEDIUM, None) is None
    pinned = shot.luma_dust_range_for_shot(STRONG, "talking_head", 720, 1280)
    assert pinned is not None
    assert (pinned.lo, pinned.hi) == (13, 13)
    wide = shot.luma_dust_range_for_shot(STRONG, "talking_head", 1080, 1920)
    assert wide is not None
    assert (wide.lo, wide.hi) == (11, 13)


def test_phone_canvas_is_instagram_720():
    assert shot.is_phone_canvas(720, 1280) is True
    assert shot.is_phone_canvas(1280, 720) is True
    assert shot.is_phone_canvas(1080, 1920) is False
    assert shot.is_phone_canvas(1920, 1080) is False
    assert shot.is_phone_canvas(None, 1280) is False
    assert shot.keeps_bottom_captions(720, 1280) is True
    assert shot.keeps_bottom_captions(1080, 1920) is False


def test_720_talking_head_crop_keep_clears_gate_without_face_zoom():
    """Centered 0.92 keep scored 20 bits on Instagram 720. 0.86–0.90 from the
    top scored 25–26. Strong stays above the banned 0.78 face-zoom."""
    from variant_maker.presets import MEDIUM, STRONG, SUBTLE

    med = shot.crop_keep_range_for_shot(MEDIUM, "talking_head", 720, 1280)
    assert med is not None
    assert (med.lo, med.hi) == (0.86, 0.90)
    strong = shot.crop_keep_range_for_shot(STRONG, "talking_head", 720, 1280)
    assert strong is not None
    assert strong.lo == 0.82
    assert strong.lo > 0.78
    assert shot.crop_keep_range_for_shot(MEDIUM, "talking_head", 1080, 1920) is None
    assert shot.crop_keep_range_for_shot(MEDIUM, "motion", 720, 1280) is None
    assert shot.crop_keep_range_for_shot(SUBTLE, None, 720, 1280) is None


def test_720_talking_head_luma_shade_stays_off():
    """lookaqmtp 8×14 c0s=100 was lava. Shade range is always None."""
    from variant_maker.presets import MEDIUM, STRONG, SUBTLE

    assert shot.luma_shade_range_for_shot(STRONG, "talking_head", 720, 1280) is None
    assert shot.luma_shade_range_for_shot(MEDIUM, "talking_head", 720, 1280) is None
    assert shot.luma_shade_range_for_shot(SUBTLE, "talking_head", 720, 1280) is None
    assert shot.luma_shade_range_for_shot(STRONG, "talking_head", 1080, 1920) is None
    assert shot.luma_shade_range_for_shot(STRONG, "motion", 720, 1280) is None
    assert shot.luma_shade_range_for_shot(STRONG, "talking_head") is None
    assert shot.luma_shade_range_for_shot(STRONG, None, 720, 1280) is None
