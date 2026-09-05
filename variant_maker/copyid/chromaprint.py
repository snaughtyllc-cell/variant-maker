"""Chromaprint audio near-duplicate head. External ``fpcalc`` only — no AcoustID."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile

from .fuse import AUDIO_POLICY_ORIGINAL_BED

AUDIO_METRIC = "chromaprint_v1"
# Match window in fingerprint *items* (fpcalc ~8192-ish samples/item at default).
MAX_OFFSET = 120
MIN_OVERLAP = 8
# Chromaprint's usual decode rate. We resample here so fpcalc does not need
# the worker image's libav to understand BtbN-encoded mp4s.
FPCALC_RATE = 11025


def _audio_base(*, score_state: str, reason: str | None = None) -> dict:
    """Unavailable / error / disabled — uniqueness stays None, never a fake 0."""
    out = {
        "uniqueness": None,
        "sim": None,
        "status": "unknown",
        "available": False,
        "metric": AUDIO_METRIC,
        "score_state": score_state,
        "policy": AUDIO_POLICY_ORIGINAL_BED,
        "diagnostic": True,
    }
    if reason:
        out["reason"] = reason
    return out


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


def _fpcalc_direct(path: str, *, length: int = 120) -> list[int]:
    proc = subprocess.run(
        ["fpcalc", "-raw", "-length", str(int(length)), path],
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_raw(proc.stdout or proc.stderr or "")


def _fpcalc_via_ffmpeg(path: str, *, length: int = 120) -> list[int]:
    """Decode with our ffmpeg, then fingerprint the wav.

    Slim Fast installs ``fpcalc`` (``libchromaprint-tools``) but its libav
    often cannot open the BtbN static-ffmpeg mp4s we actually render. Lab
    pack 3d4fae98ca77 scored audio ``available: false`` that way.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise FileNotFoundError("ffmpeg not on PATH")
    with tempfile.TemporaryDirectory(prefix="vm-fpcalc-") as td:
        wav = os.path.join(td, "a.wav")
        subprocess.run(
            [
                ffmpeg, "-v", "error", "-y", "-i", path,
                "-t", str(int(length)), "-vn",
                "-ac", "1", "-ar", str(FPCALC_RATE),
                wav,
            ],
            check=True,
            capture_output=True,
        )
        return _fpcalc_direct(wav, length=length)


def _fpcalc(path: str, *, length: int = 120) -> tuple[list[int], str]:
    try:
        return _fpcalc_direct(path, length=length), "direct"
    except (OSError, subprocess.CalledProcessError, ValueError):
        return _fpcalc_via_ffmpeg(path, length=length), "ffmpeg_wav"


def score_audio(path_a: str, path_b: str, *, length: int = 120) -> dict:
    """Audio uniqueness vs a Chromaprint match. Missing binary → unavailable.

    Picture variants keep the original bed. A high match is expected and is
    diagnostic-only — never a low uniqueness score that looks like a fail.
    """
    if not available():
        return _audio_base(score_state="unavailable", reason="no_fpcalc")
    if not os.path.isfile(path_a) or not os.path.isfile(path_b):
        return _audio_base(score_state="unavailable", reason="missing_file")
    try:
        fa, via_a = _fpcalc(path_a, length=length)
        fb, via_b = _fpcalc(path_b, length=length)
        if not fa or not fb:
            return _audio_base(score_state="unavailable", reason="empty")
        sim = match_fingerprints(fa, fb)
        uniq = 1.0 - sim
        via = "ffmpeg_wav" if "ffmpeg_wav" in (via_a, via_b) else "direct"
        return {
            "uniqueness": uniq,
            "sim": sim,
            "status": "ok",
            "available": True,
            "metric": AUDIO_METRIC,
            "score_state": "measured",
            "policy": AUDIO_POLICY_ORIGINAL_BED,
            "diagnostic": True,
            "n_a": len(fa),
            "n_b": len(fb),
            "via": via,
        }
    except (OSError, subprocess.CalledProcessError, ValueError, TypeError):
        return _audio_base(score_state="error", reason="error")
