"""Chromaprint audio near-duplicate head. External ``fpcalc`` only — no AcoustID."""
from __future__ import annotations

import os
import re
import shutil
import subprocess

AUDIO_METRIC = "chromaprint_v1"
# Match window in fingerprint *items* (fpcalc ~8192-ish samples/item at default).
MAX_OFFSET = 120
MIN_OVERLAP = 8


def available() -> bool:
    return shutil.which("fpcalc") is not None


def parse_raw(text: str) -> list[int]:
    """Parse ``fpcalc -raw`` stdout into unsigned 32-bit ints."""
    for line in (text or "").splitlines():
        if line.upper().startswith("FINGERPRINT="):
            body = line.split("=", 1)[1].strip()
            if not body:
                return []
            parts = re.split(r"[\s,]+", body)
            out: list[int] = []
            for p in parts:
                if not p:
                    continue
                out.append(int(p) & 0xFFFFFFFF)
            return out
    raise ValueError("no FINGERPRINT= line in fpcalc output")


def match_fingerprints(
    a: list[int],
    b: list[int],
    *,
    max_offset: int = MAX_OFFSET,
    min_overlap: int = MIN_OVERLAP,
) -> float:
    """Best offset-aware bit agreement in [0, 1]. Identical lists → ~1."""
    if not a or not b:
        return 0.0
    best = 0.0
    off_lo = -min(max_offset, len(b) - 1)
    off_hi = min(max_offset, len(a) - 1)
    for off in range(off_lo, off_hi + 1):
        if off >= 0:
            aa, bb = a[off:], b
        else:
            aa, bb = a, b[-off:]
        n = min(len(aa), len(bb))
        if n < min_overlap:
            continue
        dist = 0
        for i in range(n):
            dist += (aa[i] ^ bb[i]).bit_count()
        score = 1.0 - (dist / (n * 32.0))
        best = max(best, score)
    return max(0.0, min(1.0, best))


def _fpcalc(path: str, *, length: int = 120) -> list[int]:
    proc = subprocess.run(
        ["fpcalc", "-raw", "-length", str(int(length)), path],
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_raw(proc.stdout or proc.stderr or "")


def score_audio(path_a: str, path_b: str, *, length: int = 120) -> dict:
    """Audio uniqueness vs a Chromaprint match. Missing binary → unavailable."""
    base = {
        "uniqueness": None,
        "sim": None,
        "status": "unknown",
        "available": False,
        "metric": AUDIO_METRIC,
    }
    if not available():
        return base
    if not os.path.isfile(path_a) or not os.path.isfile(path_b):
        return base
    try:
        fa = _fpcalc(path_a, length=length)
        fb = _fpcalc(path_b, length=length)
        if not fa or not fb:
            return base
        sim = match_fingerprints(fa, fb)
        uniq = 1.0 - sim
        return {
            "uniqueness": uniq,
            "sim": sim,
            "status": "ok",
            "available": True,
            "metric": AUDIO_METRIC,
            "n_a": len(fa),
            "n_b": len(fb),
        }
    except (OSError, subprocess.CalledProcessError, ValueError, TypeError):
        return base
