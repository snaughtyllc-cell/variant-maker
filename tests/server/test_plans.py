"""Plan table: caps, tab flags, zero-mean messages. No ffmpeg."""
from variant_maker.server.plans import (
    PLAN_TABLE,
    QuotaSnapshot,
    blocked_reason,
    fast_limit,
    hq_limit,
    normalize_plan,
    quality_kind,
    shows_team,
    shows_workflows,
)


def test_unknown_plan_is_internal_uncapped():
    assert normalize_plan(None) == "internal"
    assert normalize_plan("") == "internal"
    assert normalize_plan("Creator") == "creator"
    assert fast_limit("internal") is None
    assert hq_limit("internal") is None


def test_creator_is_ten_by_twenty_fast_no_hq_no_team_no_workflows():
    assert PLAN_TABLE["creator"]["fast_limit_30d"] == 200
    assert fast_limit("creator") == 200
    assert hq_limit("creator") == 0
    assert shows_team("creator") is False
    assert shows_workflows("creator") is False
    assert shows_team("pro") is True
    assert shows_workflows("agency") is True


def test_override_beats_plan_default_including_zero():
    assert fast_limit("creator", 8) == 8
    assert hq_limit("creator", 2) == 2
    assert hq_limit("pro", 0) == 0


def test_creator_blocks_at_cap_with_human_sentence():
    snap = QuotaSnapshot(
        plan="creator", fast_used=180, fast_limit=200, hq_used=0, hq_limit=0,
    )
    assert blocked_reason(snap, "fast", 20) is None
    msg = blocked_reason(snap, "fast", 21)
    assert msg is not None
    assert "180 / 200" in msg
    assert "21" in msg
    assert "Jeff" in msg


def test_creator_hq_is_off():
    snap = QuotaSnapshot(
        plan="creator", fast_used=0, fast_limit=200, hq_used=0, hq_limit=0,
    )
    msg = blocked_reason(snap, "hq", 1)
    assert msg is not None
    assert "HQ is not on this plan" in msg
    assert blocked_reason(snap, "fast", 1) is None


def test_internal_never_blocks():
    snap = QuotaSnapshot(
        plan="internal", fast_used=9_999, fast_limit=None, hq_used=9_999, hq_limit=None,
    )
    assert blocked_reason(snap, "fast", 200) is None
    assert blocked_reason(snap, "hq", 20) is None


def test_quality_kind_maps_mode():
    assert quality_kind("fast") == "fast"
    assert quality_kind("HQ") == "hq"
    assert quality_kind(None) == "fast"
