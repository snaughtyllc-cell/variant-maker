"""Phase 11 auto-tune: bisection on ``sample(..., strength=…)``.

Live metric is uniqueness (SSIM bits / 64) with default target
``uniqueness.DEFAULT_TARGET`` (24/64). The cheap similarity readout is
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
    peer_ok: bool = True,
) -> tuple[float, float, float]:
    """One bisection step. Returns ``(new_lo, new_hi, next_strength)``.

    ``mid`` is ``(lo+hi)/2`` of the *current* bounds before the update.

    ``passed`` is quality only (VMAF / histogram). Source uniqueness and
    sibling ``peer_ok`` are the too-similar axes — they search stronger.
    """
    mid = (lo + hi) / 2
    if not passed:
        # Too strong (quality fail) → search milder.
        hi = mid
    elif uniqueness is None or uniqueness < target or not peer_ok:
        # Too similar vs source or vs siblings → search stronger.
        lo = mid
    else:
        # Hits quality + source + peers → try milder.
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

    ``attempt(strength) -> dict`` must include ``passed`` (bool, quality) and
    ``uniqueness`` (float | None). Optional ``peer_ok`` (default True) is the
    sibling-spread gate.

    ``best`` is the last result that passed quality AND ``uniqueness >= target``
    AND ``peer_ok``; otherwise the last result. Tags ``autotune_iters``.

    ``stop_on_clear``: Fast daily packs stop at the first full hit so a 20-pack
    does not pay five extra encodes hunting a milder strength. Source uniqueness
    alone is not a hit — twins must keep searching stronger.
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
        peer_ok = result.get("peer_ok", True)
        if (
            result.get("passed")
            and uniqueness is not None
            and uniqueness >= target
            and peer_ok
        ):
            best = result
            if stop_on_clear:
                break
        lo, hi, strength = step(
            lo, hi,
            passed=result["passed"],
            uniqueness=uniqueness,
            target=target,
            peer_ok=peer_ok,
        )
    out = best if best is not None else last
    out["autotune_iters"] = iters
    return out
