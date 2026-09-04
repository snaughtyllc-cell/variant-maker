"""Chromaprint audio near-duplicate head. External ``fpcalc`` only — no AcoustID."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import wave

AUDIO_METRIC = "chromaprint_v1"
# Decode with our ffmpeg, then fpcalc on raw PCM (not a container).
VIA_FFMPEG = "ffmpeg_s16le"
# Match window in fingerprint *items* (fpcalc ~8192-ish samples/item at default).
MAX_OFFSET = 120
MIN_OVERLAP = 8
# Chromaprint's usual decode rate. We resample here so fpcalc does not need
# the worker image's libav to understand BtbN-encoded mp4s.
FPCALC_RATE = 11025
_FFMPEG_FALLBACKS = ("/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg")


def available() -> bool:
    return shutil.which("fpcalc") is not None


def _ffmpeg_bin() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    for candidate in _FFMPEG_FALLBACKS:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise FileNotFoundError("ffmpeg not on PATH")


def _decode_text(raw) -> str:
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace")
    return str(raw)


def _fpcalc_result(proc: subprocess.CompletedProcess) -> list[int]:
    text = _decode_text(proc.stdout)
    err = _decode_text(proc.stderr)
    combined = f"{text}\n{err}"
    for blob in (text, err):
        try:
            fp = parse_raw(blob)
        except ValueError:
            fp = None
        if fp:
            return fp
    low = combined.lower()
    # Debian fpcalc on raw PCM / short wav often exits 1 with EOF after
    # it already printed FINGERPRINT= (handled above) or with none.
    if "empty fingerprint" in low or "end of file" in low:
        return []
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(
            proc.returncode, proc.args, output=proc.stdout, stderr=proc.stderr,
        )
    return []


def _exc_detail(exc: BaseException) -> str:
    """Short stderr for the record head. Pack 5ef63612aaf3 was reason=error with none."""
    err = ""
    if isinstance(exc, subprocess.CalledProcessError):
        err = _decode_text(exc.stderr if exc.stderr is not None else exc.output)
        if not err:
            err = _decode_text(exc.output)
    if not err:
        err = str(exc)
    err = " ".join(err.split())
    return f"{type(exc).__name__}: {err}"[:240]


def _write_pcm_wav(raw_path: str, wav_path: str, *, rate: int = FPCALC_RATE) -> None:
    """Classic PCM WAV (fmt 16). BtbN's wav muxer is what Debian fpcalc EOF'd."""
    with open(raw_path, "rb") as f:
        data = f.read()
    if len(data) % 2:
        data = data[:-1]
    if not data:
        raise ValueError("empty pcm")
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(rate))
        w.writeframes(data)


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
        errors="replace",
        stdin=subprocess.DEVNULL,
    )
    return _fpcalc_result(proc)


def _fpcalc_via_ffmpeg(path: str, *, length: int = 120) -> list[int]:
    """Decode with our ffmpeg to s16le, wrap a classic WAV, then fpcalc.

    Slim Fast ``fpcalc`` cannot demux BtbN mp4s. Raw ``-format s16le`` on
    Debian still exits 1: ``Error decoding audio frame (End of file)``
    (pack ``bd19fcc20eed``). A stdlib ``wave`` header gives libav a duration
    so it does not treat EOF as a failed frame.
    """
    ffmpeg = _ffmpeg_bin()
    with tempfile.TemporaryDirectory(prefix="vm-fpcalc-") as td:
        raw = os.path.join(td, "a.s16")
        wav = os.path.join(td, "a.wav")
        ff = subprocess.run(
            [
                ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-y",
                "-i", path,
                "-t", str(int(length)),
                "-map", "0:a:0",
                "-ac", "1", "-ar", str(FPCALC_RATE),
                "-f", "s16le",
                raw,
            ],
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
        )
        if ff.returncode != 0:
            raise subprocess.CalledProcessError(
                ff.returncode, ff.args, output=ff.stdout, stderr=ff.stderr,
            )
        if not os.path.isfile(raw) or os.path.getsize(raw) <= 0:
            return []
        _write_pcm_wav(raw, wav)
        try:
            fp = _fpcalc_direct(wav, length=length)
            if fp:
                return fp
        except (OSError, subprocess.CalledProcessError, ValueError):
            pass
        proc = subprocess.run(
            [
                "fpcalc", "-raw", "-length", str(int(length)),
                "-format", "s16le", "-rate", str(FPCALC_RATE),
                "-channels", "1", raw,
            ],
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
            stdin=subprocess.DEVNULL,
        )
        return _fpcalc_result(proc)


def _fpcalc(path: str, *, length: int = 120) -> tuple[list[int], str]:
    """ffmpeg-s16le first. Slim Fast fpcalc's libav cannot open our BtbN mp4s.

    Lab pack 3d4fae98ca77 / 6f506c681f8b / 5ef63612aaf3 wrote ``available:
    false`` because fpcalc still had to demux a container. Stay ``record``.
    """
    wav_fp: list[int] | None = None
    wav_err: BaseException | None = None
    try:
        wav_fp = _fpcalc_via_ffmpeg(path, length=length)
        if wav_fp:
            return wav_fp, VIA_FFMPEG
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        wav_err = exc
    try:
        fp = _fpcalc_direct(path, length=length)
        if fp:
            return fp, "direct"
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        if wav_fp is not None:
            return wav_fp, VIA_FFMPEG
        if wav_err is not None:
            raise wav_err from exc
        raise
    if wav_fp is not None:
        return wav_fp, VIA_FFMPEG
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
        via = VIA_FFMPEG if VIA_FFMPEG in (via_a, via_b) else "direct"
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
    except (OSError, subprocess.CalledProcessError, ValueError, TypeError) as exc:
        return {**base, "reason": "error", "detail": _exc_detail(exc)}
