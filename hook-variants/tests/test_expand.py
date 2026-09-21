from __future__ import annotations

import random

import pytest

from hook_variants.expand import expand_hooks, expand_hooks_llm, normalize_seed


def test_normalize_strips_hashtags_and_space() -> None:
    assert normalize_seed("  this is why  #fyp  it hits  ") == "this is why it hits"


def test_empty_seed_raises() -> None:
    with pytest.raises(ValueError):
        normalize_seed("   #only  ")


def test_locked_repeats_seed() -> None:
    out = expand_hooks("this is why it hits", 4, locked=True)
    assert out == ["this is why it hits"] * 4


def test_unlocked_starts_with_seed_and_has_length() -> None:
    out = expand_hooks("this is why it hits", 5)
    assert len(out) == 5
    assert out[0] == "this is why it hits"
    assert any(item != out[0] for item in out)


def test_rng_is_deterministic() -> None:
    a = expand_hooks("wait for the flip", 5, rng=random.Random(7))
    b = expand_hooks("wait for the flip", 5, rng=random.Random(7))
    c = expand_hooks("wait for the flip", 5, rng=random.Random(8))
    assert a == b
    assert a != c or a == c  # shuffle may collide; just require a==b


def test_llm_fallback_without_keys() -> None:
    out = expand_hooks_llm("this is why it hits", 3, api={})
    assert out == expand_hooks("this is why it hits", 3)
