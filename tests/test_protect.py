"""Phase 10 content-protection helpers — pure + gated, no SAM download."""
from __future__ import annotations

import importlib

from variant_maker.neural import protect


def test_available_is_false_without_mediapipe_or_env(monkeypatch):
    """Default: no segmenter → False. Tests must not download models."""
    monkeypatch.delenv("VARIANT_MAKER_PROTECT_BACKEND", raising=False)
    monkeypatch.setattr(protect, "_mediapipe_importable", lambda: False)
    monkeypatch.setattr(protect, "_sam_importable", lambda: False)
    monkeypatch.setattr(protect, "_opencv_importable", lambda: False)
    assert protect.available() is False


def test_available_is_true_when_backend_env_set(monkeypatch):
    """Opt-in backend name gates True without fetching weights."""
    monkeypatch.setenv("VARIANT_MAKER_PROTECT_BACKEND", "mediapipe")
    monkeypatch.setattr(protect, "_mediapipe_importable", lambda: False)
    monkeypatch.setattr(protect, "_sam_importable", lambda: False)
    monkeypatch.setattr(protect, "_opencv_importable", lambda: False)
    assert protect.available() is True


def test_available_is_true_when_mediapipe_importable(monkeypatch):
    monkeypatch.delenv("VARIANT_MAKER_PROTECT_BACKEND", raising=False)
    monkeypatch.setattr(protect, "_mediapipe_importable", lambda: True)
    monkeypatch.setattr(protect, "_sam_importable", lambda: False)
    assert protect.available() is True


def test_available_is_false_when_backend_explicitly_off(monkeypatch):
    monkeypatch.setenv("VARIANT_MAKER_PROTECT_BACKEND", "none")
    monkeypatch.setattr(protect, "_mediapipe_importable", lambda: True)
    assert protect.available() is False


def test_build_protection_mask_returns_none_when_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(protect, "available", lambda: False)
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"")
    assert protect.build_protection_mask(str(frame)) is None


def test_build_protection_mask_returns_none_without_running_sam(monkeypatch, tmp_path):
    """Even when gated on, this phase does not download or run SAM."""
    monkeypatch.setenv("VARIANT_MAKER_PROTECT_BACKEND", "sam")
    importlib.reload(protect)
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"")
    try:
        assert protect.build_protection_mask(str(frame)) is None
    finally:
        monkeypatch.delenv("VARIANT_MAKER_PROTECT_BACKEND", raising=False)
        importlib.reload(protect)


def test_mask_blocks_crop_when_coverage_at_or_above_threshold():
    assert protect.mask_blocks_crop(0.15) is True
    assert protect.mask_blocks_crop(0.40, threshold=0.15) is True
    assert protect.mask_blocks_crop(0.20, threshold=0.10) is True


def test_mask_blocks_crop_allows_crop_when_coverage_is_small():
    assert protect.mask_blocks_crop(0.0) is False
    assert protect.mask_blocks_crop(0.14, threshold=0.15) is False
    assert protect.mask_blocks_crop(0.05, threshold=0.15) is False


def test_clamp_crop_keep_is_identity_when_no_protected_edge():
    assert protect.clamp_crop_keep(0.92, 0.0) == 0.92
    assert protect.clamp_crop_keep(1.0, 0.0) == 1.0
    assert protect.clamp_crop_keep(0.80, 0) == 0.80


def test_clamp_crop_keep_does_not_punch_into_protected_edge():
    # crop_keep 0.90 would shave 10%; a 5% protected edge band forbids that depth
    kept = protect.clamp_crop_keep(0.90, 0.05)
    assert kept >= 0.95
    assert kept <= 1.0
    # already-conservative keep is unchanged (never more aggressive)
    assert protect.clamp_crop_keep(0.98, 0.05) == 0.98


def test_clamp_crop_keep_full_edge_mask_disables_crop():
    assert protect.clamp_crop_keep(0.88, 1.0) == 1.0


def test_apply_to_params_identity_when_mask_is_none(monkeypatch):
    monkeypatch.setattr(protect, "build_protection_mask", lambda *a, **k: None)
    params = {"video": {"crop_keep": 0.90}, "audio": {}}
    out = protect.apply_to_params(params)
    assert out is params
    assert out["video"]["crop_keep"] == 0.90


def test_apply_to_params_raises_crop_keep_with_mask_edge_frac():
    params = {"video": {"crop_keep": 0.90}, "audio": {}}
    out = protect.apply_to_params(params, mask_edge_frac=0.05)
    assert out["video"]["crop_keep"] >= 0.95
    assert out["video"]["crop_keep"] <= 1.0
    assert params["video"]["crop_keep"] == 0.90
    assert out is not params
    assert out["video"] is not params["video"]


def test_mask_stats_tightens_crop_when_face_is_near_edge():
    # 100x100 frame; face flush to the left edge
    stats = protect.mask_stats([(0.0, 40.0, 20.0, 80.0)], 100, 100)
    assert stats["coverage"] > 0.0
    assert stats["edge_frac"] >= 0.03
    assert protect.clamp_crop_keep(0.90, stats["edge_frac"]) >= 0.97


def test_mask_stats_center_face_does_not_force_keep_to_one():
    stats = protect.mask_stats([(40.0, 40.0, 60.0, 60.0)], 100, 100)
    assert stats["coverage"] < 0.15
    kept = protect.clamp_crop_keep(0.95, stats["edge_frac"])
    assert kept == 0.95


def test_apply_to_params_uses_built_mask_from_frame(monkeypatch):
    monkeypatch.setattr(
        protect, "build_protection_mask",
        lambda *a, **k: {"coverage": 0.04, "edge_frac": 0.08, "n_faces": 1},
    )
    params = {"video": {"crop_keep": 0.90}, "audio": {}}
    out = protect.apply_to_params(params, frame_path="mid.png")
    assert out["video"]["crop_keep"] >= 0.92
    assert params["video"]["crop_keep"] == 0.90


def test_apply_to_params_blocks_crop_when_coverage_high(monkeypatch):
    monkeypatch.setattr(
        protect, "build_protection_mask",
        lambda *a, **k: {"coverage": 0.40, "edge_frac": 0.02, "n_faces": 1},
    )
    out = protect.apply_to_params({"video": {"crop_keep": 0.90}}, frame_path="mid.png")
    assert out["video"]["crop_keep"] == 1.0


def test_detect_face_boxes_uses_injected_detector(monkeypatch, tmp_path):
    frame = tmp_path / "f.png"
    frame.write_bytes(b"x")
    monkeypatch.setattr(protect, "_detect_impl", lambda path: [(1, 2, 3, 4)])
    assert protect.detect_face_boxes(str(frame)) == [(1, 2, 3, 4)]
