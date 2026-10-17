from __future__ import annotations

from hook_variants.plan import plan_from_placement_items, plan_hooks
from hook_variants.types import SAFE_SLOTS, STYLE_IDS


def test_plan_is_deterministic() -> None:
    a = plan_hooks("this is why it hits", 5, "seed-a")
    b = plan_hooks("this is why it hits", 5, "seed-a")
    assert a.to_dict() == b.to_dict()
    assert a.count == 5
    assert len(a.hooks) == 5


def test_default_plan_skips_mid() -> None:
    plan = plan_hooks("this is why it hits", 5, "seed-b")
    assert all(hook.slot in SAFE_SLOTS for hook in plan.hooks)


def test_allow_mid_can_use_mid() -> None:
    seen = {
        hook.slot
        for i in range(6)
        for hook in plan_hooks("this is why it hits", 5, f"mid-{i}", allow_mid=True).hooks
    }
    assert "mid" in seen


def test_source_text_bottom_avoids_low() -> None:
    plan = plan_hooks("hook line", 4, "s", source_text="bottom")
    assert all(hook.slot == "top" for hook in plan.hooks)


def test_locked_marks_source_and_same_text() -> None:
    plan = plan_hooks("Same Line", 3, "s", locked=True)
    assert {h.text for h in plan.hooks} == {"Same Line"}
    assert all(h.source == "lock" for h in plan.hooks)


def test_named_style_on_every_hook() -> None:
    plan = plan_hooks("hook line", 4, "s", style_id="edits-strong")
    assert all(h.style_id == "edits-strong" for h in plan.hooks)


def test_auto_uses_known_styles() -> None:
    plan = plan_hooks("hook line", 5, "s")
    assert {h.style_id for h in plan.hooks} <= set(STYLE_IDS)


def test_adjacent_avoid_same_style_and_slot() -> None:
    plan = plan_hooks("hook line", 5, "spread")
    for prev, cur in zip(plan.hooks, plan.hooks[1:]):
        same = prev.style_id == cur.style_id and prev.slot == cur.slot
        assert not same


def test_plan_from_placement_list() -> None:
    plan = plan_from_placement_items(
        [
            {"text": "one", "style_id": "tiktok-classic-box", "slot": "top"},
            {"text": "two", "style_id": "edits-strong", "slot": "mid"},
        ],
        seed_text="one",
        master_seed="p",
    )
    assert plan.count == 2
    assert plan.hooks[1].slot == "mid"
