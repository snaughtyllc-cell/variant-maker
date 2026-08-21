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
