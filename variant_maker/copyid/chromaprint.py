"""Chromaprint audio near-duplicate head. External ``fpcalc`` only — no AcoustID."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile

AUDIO_METRIC = "chromaprint_v1"
# Match window in fingerprint *items* (fpcalc ~8192-ish samples/item at default).
MAX_OFFSET = 120
MIN_OVERLAP = 8
# Chromaprint's usual decode rate. We resample here so fpcalc does not need
# the worker image's libav to understand BtbN-encoded mp4s.
FPCALC_RATE = 11025


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
        check=False,
        capture_output=True,
        text=True,
    )
    text = proc.stdout or ""
    err = proc.stderr or ""
    combined = f"{text}\n{err}".lower()
    if proc.returncode != 0:
        if "empty fingerprint" in combined:
            return []
        raise subprocess.CalledProcessError(
            proc.returncode, proc.args, output=proc.stdout, stderr=proc.stderr,
        )
    if not text.strip():
        return []
    return parse_raw(text or err)


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
                "-c:a", "pcm_s16le",
                wav,
            ],
            check=True,
            capture_output=True,
        )
        return _fpcalc_direct(wav, length=length)


def _fpcalc(path: str, *, length: int = 120) -> tuple[list[int], str]:
    """Wav-first. Slim Fast fpcalc's libav cannot open our BtbN mp4s.

    Lab pack 3d4fae98ca77 / 6f506c681f8b wrote ``available: false`` because
    direct fpcalc ran first and errored; empty fingerprints were not a miss.
    Stay ``record`` — this only has to *score*.
    """
    wav_fp: list[int] | None = None
    wav_err: BaseException | None = None
    try:
        wav_fp = _fpcalc_via_ffmpeg(path, length=length)
        if wav_fp:
            return wav_fp, "ffmpeg_wav"
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        wav_err = exc
    try:
        fp = _fpcalc_direct(path, length=length)
        if fp:
            return fp, "direct"
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        if wav_fp is not None:
            return wav_fp, "ffmpeg_wav"
        if wav_err is not None:
            raise wav_err from exc
        raise
    if wav_fp is not None:
        return wav_fp, "ffmpeg_wav"
    return [], "direct"


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
        return {**base, "reason": "no_fpcalc"}
    if not os.path.isfile(path_a) or not os.path.isfile(path_b):
        return {**base, "reason": "missing_file"}
    try:
        fa, via_a = _fpcalc(path_a, length=length)
        fb, via_b = _fpcalc(path_b, length=length)
        if not fa or not fb:
            return {**base, "reason": "empty"}
        sim = match_fingerprints(fa, fb)
        uniq = 1.0 - sim
        via = "ffmpeg_wav" if "ffmpeg_wav" in (via_a, via_b) else "direct"
        return {
            "uniqueness": uniq,
            "sim": sim,
            "status": "ok",
            "available": True,
            "metric": AUDIO_METRIC,
            "n_a": len(fa),
            "n_b": len(fb),
            "via": via,
        }
    except (OSError, subprocess.CalledProcessError, ValueError, TypeError):
        return {**base, "reason": "error"}
