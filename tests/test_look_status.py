"""Look status vocabulary — pure, no ffmpeg."""
from __future__ import annotations

from variant_maker.look import (
    LOOK_LUMA_MAX,
    STATUS_NO_ALARM,
    STATUS_REVIEW_REQUIRED,
    STATUS_UNKNOWN,
    approval_valid,
    blocks_unattended_escalate,
    classify_mae,
    event_fields,
    look_is_deliverable,
    normalize_look_status,
    review_playback,
)


def test_mae_threshold_stays_38():
    assert LOOK_LUMA_MAX == 38.0
    assert classify_mae(38.0) == STATUS_NO_ALARM
    assert classify_mae(38.01) == STATUS_REVIEW_REQUIRED
    assert classify_mae(12.0) == STATUS_NO_ALARM


def test_legacy_ok_fail_normalize():
    assert normalize_look_status("ok") == STATUS_NO_ALARM
    assert normalize_look_status("fail") == STATUS_REVIEW_REQUIRED
    assert normalize_look_status("review_required") == STATUS_REVIEW_REQUIRED
    assert normalize_look_status("no_coarse_luma_alarm") == STATUS_NO_ALARM
    assert normalize_look_status("unknown") == STATUS_UNKNOWN
    assert normalize_look_status(None) == STATUS_UNKNOWN


def test_review_required_blocks_unattended_escalate_legacy_fail_too():
    assert blocks_unattended_escalate("review_required") is True
    assert blocks_unattended_escalate("fail") is True
    assert blocks_unattended_escalate("ok") is False
    assert blocks_unattended_escalate("no_coarse_luma_alarm") is False
    assert blocks_unattended_escalate("unknown") is False


def test_unknown_is_not_look_approved_or_deliverable():
    assert look_is_deliverable("unknown") is False
    assert look_is_deliverable("no_coarse_luma_alarm") is True
    assert look_is_deliverable("ok") is True
    assert look_is_deliverable("review_required") is False
    assert look_is_deliverable(
        "review_required", artifact_sha="aaa", approved_sha="aaa",
    ) is True
    assert look_is_deliverable(
        "review_required", artifact_sha="aaa", approved_sha="bbb",
    ) is False


def test_approval_invalidates_when_encode_changes():
    assert approval_valid("abc", "abc") is True
    assert approval_valid("abc", "def") is False
    assert approval_valid("abc", None) is False
    assert approval_valid(None, "abc") is False


def test_review_playback_uses_worst_mae_timestamp():
    frames = [
        {"frac": 0.25, "t_src": 1.0, "t_var": 1.0, "mae": 12.0},
        {"frac": 0.50, "t_src": 2.0, "t_var": 2.0, "mae": 51.0},
        {"frac": 0.75, "t_src": 3.0, "t_var": 3.0, "mae": 20.0},
    ]
    win = review_playback(frames, duration_s=4.0, pad_s=0.75)
    assert win is not None
    assert win["t"] == 2.0
    assert win["start"] == 1.25
    assert win["end"] == 2.75


def test_event_fields_bind_review_t_to_worst_frame():
    info = {
        "look_status": STATUS_REVIEW_REQUIRED,
        "look_mae": 27.0,
        "look_mae_max": 51.0,
        "look_src": "look_v01_src.jpg",
        "look_var": "look_v01.jpg",
        "look_artifact_sha256": "abc",
        "look_frames": [
            {"frac": 0.25, "t_src": 1.0, "t_var": 1.0, "mae": 12.0},
            {"frac": 0.50, "t_src": 2.0, "t_var": 2.0, "mae": 51.0},
            {"frac": 0.75, "t_src": 3.0, "t_var": 3.0, "mae": 20.0},
        ],
    }
    out = event_fields(info, duration_s=4.0)
    assert out["look_status"] == STATUS_REVIEW_REQUIRED
    assert out["look_mae_max"] == 51.0
    assert out["look_artifact_sha256"] == "abc"
    assert out["look_review_t"] == 2.0
    assert len(out["look_frames"]) == 3
