"""Phase 11 auto-tune: bisection on ``sample(..., strength=…)``.

Live metric is uniqueness (SSIM bits / 64) with default target
``uniqueness.DEFAULT_TARGET`` (0.375). The cheap similarity readout is
``1 - uniqueness`` (see ``uniqueness.similarity_from_uniqueness``). The live
gate stays on uniqueness — switching it to a 35% similarity (Path-B) cutoff
would trash Fast look. Path-B 35% is a later calibration, not this controller.

PURE: ``tune`` injects ``attempt(strength) -> dict``; no ffmpeg.
"""
from __future__ import annotations


def step(
    lo: float,
    hi: float,
    *,
    passed: bool,
    uniqueness: float | None,
    target: float,
) -> tuple[float, float, float]:
    """One bisection step. Returns ``(new_lo, new_hi, next_strength)``.

    ``mid`` is ``(lo+hi)/2`` of the *current* bounds before the update.
    """
    mid = (lo + hi) / 2
    if not passed:
        # Too strong (quality / combined gate fail) → search milder.
        hi = mid
    elif uniqueness is None or uniqueness < target:
        # Too similar → search stronger.
        lo = mid
    else:
        # Hits both → try milder.
        hi = mid
    return lo, hi, (lo + hi) / 2


def tune(
    attempt,
    *,
    target: float,
    lo: float = 0.5,
    hi: float = 1.8,
    max_iters: int = 5,
    min_span: float = 0.05,
    stop_on_clear: bool = False,
) -> dict:
    """Bisect strength until uniqueness clears ``target`` (or ``max_iters``).

    ``attempt(strength) -> dict`` must include ``passed`` (bool) and
    ``uniqueness`` (float | None).

    ``best`` is the last result that passed AND ``uniqueness >= target``;
    otherwise the last result. Tags ``autotune_iters`` on the returned dict.

    ``stop_on_clear``: Fast daily packs stop at the first hit so a 20-pack does
    not pay five extra encodes hunting a milder strength.
    """
    strength = (lo + hi) / 2
    best = None
    last = None
    iters = 0
    for _ in range(max_iters):
        if last is not None and (hi - lo) < min_span:
            break
        result = attempt(strength)
        iters += 1
        last = result
        uniqueness = result.get("uniqueness")
        if result.get("passed") and uniqueness is not None and uniqueness >= target:
            best = result
            if stop_on_clear:
                break
        lo, hi, strength = step(
            lo, hi, passed=result["passed"], uniqueness=uniqueness, target=target,
        )
    out = best if best is not None else last
    out["autotune_iters"] = iters
    return out
