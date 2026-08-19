"""Phase 11 auto-tune controller: pure bisection on injected attempt() — no ffmpeg."""
from __future__ import annotations

from variant_maker import autotune
from variant_maker.uniqueness import DEFAULT_TARGET


def test_step_not_passed_is_too_strong():
    lo0, hi0 = 0.5, 1.8
    mid = (lo0 + hi0) / 2
    lo, hi, nxt = autotune.step(lo0, hi0, passed=False, uniqueness=0.9, target=DEFAULT_TARGET)
    assert lo == lo0
    assert hi == mid
    assert nxt == (lo + hi) / 2


def test_step_below_target_is_too_similar():
    lo0, hi0 = 0.5, 1.8
    mid = (lo0 + hi0) / 2
    lo, hi, nxt = autotune.step(lo0, hi0, passed=True, uniqueness=0.1, target=DEFAULT_TARGET)
    assert lo == mid
    assert hi == hi0
    assert nxt == (lo + hi) / 2


def test_step_none_uniqueness_is_too_similar():
    lo0, hi0 = 0.5, 1.8
    mid = (lo0 + hi0) / 2
    lo, hi, nxt = autotune.step(lo0, hi0, passed=True, uniqueness=None, target=DEFAULT_TARGET)
    assert lo == mid
    assert hi == hi0
    assert nxt == (lo + hi) / 2


def test_step_hits_both_tries_milder():
    lo0, hi0 = 0.5, 1.8
    mid = (lo0 + hi0) / 2
    lo, hi, nxt = autotune.step(lo0, hi0, passed=True, uniqueness=0.5, target=DEFAULT_TARGET)
    assert lo == lo0
    assert hi == mid
    assert nxt == (lo + hi) / 2


def test_step_peer_fail_is_too_similar():
    """Quality + source uniqueness clear, but siblings are twins → search stronger."""
    lo0, hi0 = 0.5, 1.8
    mid = (lo0 + hi0) / 2
    lo, hi, nxt = autotune.step(
        lo0, hi0, passed=True, uniqueness=0.5, target=DEFAULT_TARGET, peer_ok=False,
    )
    assert lo == mid
    assert hi == hi0
    assert nxt == (lo + hi) / 2


def test_step_quality_fail_beats_peer_fail():
    """VMAF miss still searches milder even when peers also fail."""
    lo0, hi0 = 0.5, 1.8
    mid = (lo0 + hi0) / 2
    lo, hi, nxt = autotune.step(
        lo0, hi0, passed=False, uniqueness=0.5, target=DEFAULT_TARGET, peer_ok=False,
    )
    assert lo == lo0
    assert hi == mid
    assert nxt == (lo + hi) / 2


def test_step_uniqueness_at_target_counts_as_hit():
    lo0, hi0 = 0.0, 2.0
    mid = (lo0 + hi0) / 2
    lo, hi, nxt = autotune.step(lo0, hi0, passed=True, uniqueness=DEFAULT_TARGET, target=DEFAULT_TARGET)
    assert hi == mid
    assert lo == lo0
    assert nxt == (lo + hi) / 2


def test_tune_never_clearing_returns_last_and_tags_iters():
    seen = []

    def attempt(strength):
        seen.append(strength)
        return {"passed": True, "uniqueness": 0.1, "mark": len(seen)}

    out = autotune.tune(attempt, target=DEFAULT_TARGET, max_iters=3)
    assert out["mark"] == 3
    assert out["uniqueness"] == 0.1
    assert out["autotune_iters"] == 3
    assert len(seen) == 3


def test_tune_keeps_last_result_that_cleared_not_later_miss():
    seen = []

    def attempt(strength):
        seen.append(strength)
        n = len(seen)
        if n == 1:
            return {"passed": True, "uniqueness": 0.1, "id": 1}
        if n == 2:
            return {"passed": True, "uniqueness": 0.5, "id": 2}
        return {"passed": True, "uniqueness": 0.1, "id": n}

    out = autotune.tune(attempt, target=DEFAULT_TARGET, max_iters=4)
    assert out["id"] == 2
    assert out["uniqueness"] == 0.5
    assert out["autotune_iters"] == 4
    assert len(seen) == 4


def test_tune_quality_fail_is_not_best_even_if_unique():
    def attempt(strength):
        return {"passed": False, "uniqueness": 0.9, "s": strength}

    out = autotune.tune(attempt, target=DEFAULT_TARGET, max_iters=2)
    assert out["passed"] is False
    assert out["autotune_iters"] == 2


def test_tune_min_span_stops_after_first_when_already_tight():
    n = {"c": 0}

    def attempt(strength):
        n["c"] += 1
        return {"passed": True, "uniqueness": 0.5}

    out = autotune.tune(
        attempt, target=DEFAULT_TARGET, lo=1.0, hi=1.02, max_iters=5, min_span=0.05,
    )
    assert n["c"] == 1
    assert out["autotune_iters"] == 1
    assert out["passed"] is True


def test_tune_stop_on_clear_does_not_hunt_milder():
    seen = []

    def attempt(strength):
        seen.append(strength)
        return {"passed": True, "uniqueness": 0.5, "id": len(seen)}

    out = autotune.tune(
        attempt, target=DEFAULT_TARGET, max_iters=5, stop_on_clear=True,
    )
    assert out["id"] == 1
    assert out["autotune_iters"] == 1
    assert len(seen) == 1


def test_tune_stop_on_clear_does_not_stop_when_peers_fail():
    """Source uniqueness is not enough — twins must keep searching stronger."""
    seen = []

    def attempt(strength):
        seen.append(strength)
        n = len(seen)
        return {
            "passed": True,
            "uniqueness": 0.5,
            "peer_ok": n >= 2,
            "id": n,
        }

    out = autotune.tune(
        attempt, target=DEFAULT_TARGET, max_iters=5, stop_on_clear=True,
    )
    assert out["id"] == 2
    assert out["peer_ok"] is True
    assert out["autotune_iters"] == 2
    assert len(seen) == 2
    assert seen[1] > seen[0]


def test_tune_peer_fail_is_not_best_even_if_source_unique():
    seen = []

    def attempt(strength):
        seen.append(strength)
        n = len(seen)
        if n == 1:
            return {"passed": True, "uniqueness": 0.5, "peer_ok": False, "id": 1}
        return {"passed": True, "uniqueness": 0.1, "peer_ok": False, "id": n}

    out = autotune.tune(attempt, target=DEFAULT_TARGET, max_iters=3)
    assert out["id"] != 1
    assert out["peer_ok"] is False
    assert out["autotune_iters"] == 3


def test_tune_starts_at_mid_of_bounds():
    seen = []

    def attempt(strength):
        seen.append(strength)
        return {"passed": True, "uniqueness": 0.5}

    autotune.tune(attempt, target=DEFAULT_TARGET, lo=0.5, hi=1.8, max_iters=1)
    assert seen == [(0.5 + 1.8) / 2]
