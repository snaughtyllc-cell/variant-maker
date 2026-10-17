"""Overlay planner. Pure. Same inputs → same OverlayPlan."""

from __future__ import annotations

import hashlib
import random
from dataclasses import replace

from hook_variants.expand import expand_hooks, normalize_seed
from hook_variants.types import (
    SAFE_SLOTS,
    SLOTS,
    STYLE_IDS,
    HookParams,
    OverlayPlan,
    Slot,
)

_VALID_SOURCE_TEXT = frozenset({"none", "bottom", "top"})
_MIN_COUNT = 1
_MAX_COUNT = 8


def _as_seed_int(master_seed: str | int) -> int:
    if isinstance(master_seed, int) and not isinstance(master_seed, bool):
        return master_seed
    digest = hashlib.sha256(str(master_seed).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _clamp_count(count: int) -> int:
    try:
        value = int(count)
    except (TypeError, ValueError):
        value = 5
    return max(_MIN_COUNT, min(_MAX_COUNT, value))


def _slot_pool(source_text: str, allow_mid: bool) -> tuple[Slot, ...]:
    if source_text == "bottom":
        slots: list[Slot] = ["top"]
    elif source_text == "top":
        slots = ["low"]
    else:
        slots = list(SAFE_SLOTS)
    if allow_mid and "mid" not in slots:
        slots.append("mid")
    if not allow_mid:
        slots = [s for s in slots if s != "mid"]
    return tuple(slots) or SAFE_SLOTS


def _assign_hooks(
    texts: list[str],
    *,
    rng: random.Random,
    style_id: str | None,
    slots: tuple[Slot, ...],
    source: str,
) -> list[HookParams]:
    start = rng.randrange(len(STYLE_IDS))
    slot_start = rng.randrange(len(slots))
    locked_style = style_id not in (None, "", "auto")
    hooks: list[HookParams] = []
    for i, text in enumerate(texts):
        sid = style_id if locked_style else STYLE_IDS[(start + i) % len(STYLE_IDS)]
        slot = slots[(i + slot_start) % len(slots)]
        if hooks:
            prev = hooks[-1]
            if prev.style_id == sid and prev.slot == slot:
                if len(slots) > 1:
                    slot = slots[(i + slot_start + 1) % len(slots)]
                elif not locked_style:
                    sid = STYLE_IDS[(start + i + 1) % len(STYLE_IDS)]
        hooks.append(
            HookParams(
                index=i,
                text=text,
                style_id=sid,
                slot=slot,
                source=source,
            )
        )
    return hooks


def plan_hooks(
    seed_text: str,
    count: int,
    master_seed: str | int,
    *,
    locked: bool = False,
    source_text: str = "none",
    allow_mid: bool = False,
    style_id: str | None = None,
) -> OverlayPlan:
    """Build a deterministic :class:`OverlayPlan` from a seed line."""
    source_key = (source_text or "none").strip().lower()
    if source_key not in _VALID_SOURCE_TEXT:
        raise ValueError('source_text must be "none", "bottom", or "top"')

    normalized = normalize_seed(seed_text)
    n = _clamp_count(count)
    # expand_hooks only accepts 1..5; pad by cycling if the plan wants more.
    expand_n = min(5, n)
    seed_int = _as_seed_int(master_seed)
    rng = random.Random(seed_int)
    texts = expand_hooks(normalized, expand_n, locked=locked, rng=rng)
    if not texts:
        raise ValueError("empty hook text")
    if len(texts) < n:
        texts = [texts[i % len(texts)] for i in range(n)]
    else:
        texts = texts[:n]

    source = "lock" if locked else "expand"
    hooks = _assign_hooks(
        texts,
        rng=rng,
        style_id=style_id,
        slots=_slot_pool(source_key, allow_mid),
        source=source,
    )
    return OverlayPlan(
        seed_text=normalized,
        count=len(hooks),
        master_seed=str(master_seed),
        hooks=hooks,
        locked=locked,
        source_text=source_key,
    )


def apply_style_override(plan: OverlayPlan, style_id: str) -> OverlayPlan:
    """Force every hook to ``style_id`` (CLI ``--preset``)."""
    if style_id in (None, "", "auto"):
        return plan
    hooks = [replace(h, style_id=style_id) for h in plan.hooks]
    return replace(plan, hooks=hooks)


def apply_slot_override(plan: OverlayPlan, slot: Slot) -> OverlayPlan:
    """Force every hook to ``slot`` (placement.json)."""
    hooks = [replace(h, slot=slot) for h in plan.hooks]
    return replace(plan, hooks=hooks)


def plan_from_placement_items(
    items: list[dict[str, object]],
    *,
    seed_text: str,
    master_seed: str | int,
    locked: bool = False,
    source_text: str = "none",
) -> OverlayPlan:
    """Build a plan from a JSON list of ``{text, style_id, slot}``."""
    from hook_variants.types import SLOT_Y

    source = "lock" if locked else "expand"
    try:
        normalized = normalize_seed(seed_text) if seed_text else ""
    except ValueError:
        normalized = ""
    hooks: list[HookParams] = []
    for i, item in enumerate(items[:_MAX_COUNT]):
        if not isinstance(item, dict):
            continue
        raw_text = str(item.get("text") or "").strip()
        if not raw_text:
            continue
        if locked:
            text = normalized or raw_text
        else:
            try:
                text = normalize_seed(raw_text)
            except ValueError:
                continue
        sid = str(item.get("style_id") or STYLE_IDS[i % len(STYLE_IDS)])
        slot_raw = str(item.get("slot") or SAFE_SLOTS[i % len(SAFE_SLOTS)])
        slot: Slot = slot_raw if slot_raw in SLOT_Y else SAFE_SLOTS[i % len(SAFE_SLOTS)]
        hooks.append(
            HookParams(
                index=len(hooks),
                text=text,
                style_id=sid,
                slot=slot,
                source=source,
            )
        )
    if not hooks:
        raise ValueError("placement list produced no hooks")
    if not normalized:
        normalized = hooks[0].text
    return OverlayPlan(
        seed_text=normalized,
        count=len(hooks),
        master_seed=str(master_seed),
        hooks=hooks,
        locked=locked,
        source_text=source_text or "none",
    )
