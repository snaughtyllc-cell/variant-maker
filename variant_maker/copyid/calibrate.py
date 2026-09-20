"""Clip-agnostic CopyID calibration: identity re-encode vs an unrelated pair.

Local SSIM bits and Chromaprint 0.7x scores are not a platform verdict until
those two controls exist for the clip that actually failed. Do not retune from
old look-pack talking-head files — those are not the flagged set.
"""
from __future__ import annotations

import subprocess
from collections.abc import Callable

COPY_SIM_FLOOR = 0.90
DISTINCT_SIM_CEIL = 0.55
MIN_SIM_GAP = 0.15

COPY_BITS_CEIL = 8
DISTINCT_BITS_FLOOR = 24
MIN_BITS_GAP = 8

# Grain and 576-canvas uniqueness typically vanish around here.
PLATFORM_PROXY_SIZE = 224


def platform_proxy_canvas(size: int = PLATFORM_PROXY_SIZE) -> tuple[int, int]:
    """Even square used as a cheap platform-resolution SSIM proxy."""
    s = max(2, int(size) - (int(size) % 2))
    return (s, s)


def _skipped(kind: str) -> dict:
    return {
        "kind": kind,
        "reencode": None,
        "unrelated": None,
        "gap": None,
        "separates": False,
        "status": "skipped",
        "available": False,
    }


def interpret_sim(
    reencode: float | None,
    unrelated: float | None,
    *,
    copy_floor: float = COPY_SIM_FLOOR,
    distinct_ceil: float = DISTINCT_SIM_CEIL,
    min_gap: float = MIN_SIM_GAP,
) -> dict:
    """Similarity head: 1.0 = copy-like. Needs both controls."""
    out = {
        "kind": "sim",
        "reencode": reencode,
        "unrelated": unrelated,
        "gap": None,
        "copy_floor": copy_floor,
        "distinct_ceil": distinct_ceil,
        "min_gap": min_gap,
        "separates": False,
        "status": "unknown",
        "available": False,
    }
    if reencode is None or unrelated is None:
        return out
    re_s = float(reencode)
    un_s = float(unrelated)
    gap = re_s - un_s
    out.update(reencode=re_s, unrelated=un_s, gap=gap, available=True)
    if gap <= -min_gap:
        out["status"] = "inverted"
        return out
    if abs(gap) < min_gap:
        out["status"] = "collapsed"
        return out
    if re_s >= copy_floor and un_s <= distinct_ceil and gap >= min_gap:
        out["separates"] = True
        out["status"] = "separates"
        return out
    out["status"] = "weak"
    return out


def interpret_bits(
    reencode: int | None,
    unrelated: int | None,
    *,
    copy_ceil: int = COPY_BITS_CEIL,
    distinct_floor: int = DISTINCT_BITS_FLOOR,
    min_gap: int = MIN_BITS_GAP,
) -> dict:
    """SSIM bits: low = copy-like. Needs both controls."""
    out = {
        "kind": "bits",
        "reencode": reencode,
        "unrelated": unrelated,
        "gap": None,
        "copy_ceil": copy_ceil,
        "distinct_floor": distinct_floor,
        "min_gap": min_gap,
        "separates": False,
        "status": "unknown",
        "available": False,
    }
    if reencode is None or unrelated is None:
        return out
    re_b = int(reencode)
    un_b = int(unrelated)
    gap = un_b - re_b
    out.update(reencode=re_b, unrelated=un_b, gap=gap, available=True)
    if gap <= -min_gap:
        out["status"] = "inverted"
        return out
    if abs(gap) < min_gap:
        out["status"] = "collapsed"
        return out
    if re_b <= copy_ceil and un_b >= distinct_floor and gap >= min_gap:
        out["separates"] = True
        out["status"] = "separates"
        return out
    out["status"] = "weak"
    return out


def _score_ssim_pair(
    src: str,
    reencode: str,
    unrelated: str,
    *,
    canvas: tuple[int, int] | None = None,
) -> dict:
    from variant_maker.uniqueness import bits_vs

    try:
        re_bits = bits_vs(src, reencode, canvas=canvas)
        un_bits = bits_vs(src, unrelated, canvas=canvas)
    except (OSError, ValueError, TypeError, subprocess.CalledProcessError):
        return interpret_bits(None, None)
    return interpret_bits(re_bits, un_bits)


def _head_sim(head: dict | None) -> float | None:
    if not head or head.get("available") is False:
        return None
    sim = head.get("sim")
    return None if sim is None else float(sim)


def calibrate_paths(
    src: str,
    reencode: str,
    unrelated: str,
    *,
    audio: bool = True,
    visual_backend=None,
    extract_fn: Callable | None = None,
    score_audio_fn: Callable | None = None,
    score_ssim: bool = True,
) -> dict:
    """Score identity re-encode vs unrelated on whatever heads we can run.

    ``src`` should be the clip that failed, not a historical look-pack stand-in.
    """
    ssim = _score_ssim_pair(src, reencode, unrelated) if score_ssim else _skipped("bits")
    proxy = (
        _score_ssim_pair(src, reencode, unrelated, canvas=platform_proxy_canvas())
        if score_ssim else _skipped("bits")
    )

    if not audio:
        audio_rep = _skipped("sim")
    else:
        score_fn = score_audio_fn
        if score_fn is None:
            from .chromaprint import score_audio as score_fn
        audio_rep = interpret_sim(
            _head_sim(score_fn(src, reencode)),
            _head_sim(score_fn(src, unrelated)),
        )

    if visual_backend is None:
        visual_rep = _skipped("sim")
    else:
        from .backends import score_visual
        visual_rep = interpret_sim(
            _head_sim(score_visual(
                src, reencode, visual_backend, extract_fn=extract_fn,
            )),
            _head_sim(score_visual(
                src, unrelated, visual_backend, extract_fn=extract_fn,
            )),
        )

    return {
        "ssim": ssim,
        "ssim_proxy_224": proxy,
        "audio": audio_rep,
        "visual": visual_rep,
        "separates": any(
            h.get("separates") for h in (ssim, audio_rep, visual_rep)
        ),
    }
