"""Local video uniqueness scorer: TikFusion-aligned SSIM "bits" via ffmpeg.

Samples 3 frames at 25% / 50% / 75% of duration, scales to a fixed size, runs
ffmpeg SSIM per pair, then converts like TikFusion:

    bits = round((1 - mean_ssim) * 64)

Higher bits = more different. This improves local duplicate-resilience tuning;
it does not guarantee platform accept rates.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile

METRIC_VERSION = "ssim_bits_v1"
# TikFusion Smart Detector floor ≈ 18 bits (~28% unique). VaryForge defaults
# above that for top-tail resilience: 32 bits = 50% unique (32/64 = 0.5).
# Local uniqueness gate only — not a platform verdict.
TARGET_BITS = 32
DEFAULT_TARGET = TARGET_BITS / 64.0  # 32/64 = 0.5
# Same-batch peer floor. TikFusion uses 8; 18 did not bite Fast packs (siblings
# already cleared ~35 vs source). 24 is the old source floor — spread v02 vs v01.
MIN_PEER_BITS = 24
DEFAULT_PEER = MIN_PEER_BITS  # alias
MAX_PASSES = 3
FRAME_FRACS = (0.25, 0.50, 0.75)
# Vertical TikTok/Reels-ish canvas used for pairwise SSIM.
SSIM_WIDTH = 576
SSIM_HEIGHT = 1024

_SSIM_ALL_RE = re.compile(r"SSIM\s+(?:Y|R):[^\n]*?\sAll:([0-9.]+)")


def _probe_duration(path: str) -> float:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    raw = out.stdout.strip()
    if not raw or raw.upper() == "N/A":
        raise ValueError(f"no valid duration in ffprobe output: {raw!r}")
    try:
        duration = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"no valid duration in ffprobe output: {raw!r}") from exc
    return max(duration, 0.1)


def bits_from_ssim(mean_ssim: float) -> int:
    """TikFusion conversion: bits ∈ [0, 64], higher = more different."""
    return int(round((1.0 - float(mean_ssim)) * 64))


def similarity_from_uniqueness(uniqueness: float) -> float:
    """Cheap Path-B readout: similarity = 1 − uniqueness (same SSIM-bits scale)."""
    return 1.0 - float(uniqueness)


def _extract_frame(path: str, t: float, out_path: str) -> None:
    """Extract one scaled frame near ``t`` seconds. Falls back to t=0 if seek misses."""
    vf = (
        f"scale={SSIM_WIDTH}:{SSIM_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={SSIM_WIDTH}:{SSIM_HEIGHT}:(ow-iw)/2:(oh-ih)/2"
    )
    last_err: subprocess.CalledProcessError | None = None
    # Post-input -ss is more reliable on short clips; retry t=0 if the seek is past EOF.
    for seek in (max(0.0, t), 0.0):
        if os.path.exists(out_path):
            os.remove(out_path)
        try:
            subprocess.run(
                [
                    "ffmpeg", "-v", "error",
                    "-i", path,
                    "-ss", f"{seek:.6f}",
                    "-vf", vf,
                    "-frames:v", "1",
                    "-y", out_path,
                ],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            last_err = exc
            continue
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return
    if last_err is not None:
        raise last_err
    raise ValueError(f"failed to extract frame at t={t} from {path}")



def _ssim_pair(ref_path: str, dist_path: str) -> float:
    """Return All-channel SSIM for two still images (0..1)."""
    proc = subprocess.run(
        [
            "ffmpeg", "-v", "info",
            "-i", ref_path,
            "-i", dist_path,
            "-lavfi", "ssim",
            "-f", "null", "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    # SSIM line is on stderr for ffmpeg.
    text = (proc.stderr or "") + (proc.stdout or "")
    match = _SSIM_ALL_RE.search(text)
    if not match:
        raise ValueError(f"no SSIM All= value in ffmpeg output: {text[-500]!r}")
    return float(match.group(1))


def mean_ssim(path_a: str, path_b: str) -> float:
    """Mean SSIM across the three TikFusion-aligned sample points."""
    dur_a = _probe_duration(path_a)
    dur_b = _probe_duration(path_b)
    with tempfile.TemporaryDirectory(prefix="vm-ssim-") as tmp:
        scores: list[float] = []
        for i, frac in enumerate(FRAME_FRACS):
            fa = os.path.join(tmp, f"a_{i}.png")
            fb = os.path.join(tmp, f"b_{i}.png")
            _extract_frame(path_a, frac * dur_a, fa)
            _extract_frame(path_b, frac * dur_b, fb)
            scores.append(_ssim_pair(fa, fb))
        return sum(scores) / len(scores)


def bits_vs(path_a: str, path_b: str) -> int:
    """SSIM bits between two videos (TikFusion-style). Raises on probe/ffmpeg failure."""
    return bits_from_ssim(mean_ssim(path_a, path_b))


def score_uniqueness(
    src_path: str,
    variant_path: str,
    *,
    target: float | None = None,
    n_frames: int | None = None,  # retained for call-site compat; ignored (fixed 3 frames)
) -> dict:
    """Score variant uniqueness vs source.

    Returns uniqueness ∈ [0, 1] as bits/64, plus raw ``bits`` for logs/tests.
    """
    del n_frames  # fixed FRAME_FRACS — kept in signature for older callers
    base = {
        "uniqueness": None,
        "uniqueness_status": "unknown",
        "uniqueness_metric": METRIC_VERSION,
        "uniqueness_target": target,
        "bits": None,
    }
    try:
        bits = bits_vs(src_path, variant_path)
        score = max(0.0, min(1.0, bits / 64.0))
        if target is None:
            status = "ok"
        elif score >= target:
            status = "ok"
        else:
            status = "below_target"
        return {
            "uniqueness": score,
            "uniqueness_status": status,
            "uniqueness_metric": METRIC_VERSION,
            "uniqueness_target": target,
            "bits": bits,
        }
    except (OSError, subprocess.CalledProcessError, ValueError, TypeError):
        return base
