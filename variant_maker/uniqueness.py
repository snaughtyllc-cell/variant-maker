"""Local video uniqueness scorer: aHash + luma histogram via ffmpeg frame extracts."""
from __future__ import annotations

import subprocess

METRIC_VERSION = "phash_hist_v1"


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


def extract_gray_frames(path: str, *, n: int = 10, size: int = 32) -> list[bytes]:
    duration = _probe_duration(path)
    frames: list[bytes] = []
    expected = size * size
    for i in range(n):
        t = (i + 0.5) / n * duration
        out = subprocess.run(
            [
                "ffmpeg", "-v", "error",
                "-ss", str(t),
                "-i", path,
                "-vf", f"scale={size}:{size},format=gray",
                "-frames:v", "1",
                "-f", "rawvideo", "-",
            ],
            check=True,
            capture_output=True,
        )
        if len(out.stdout) != expected:
            return []
        frames.append(out.stdout)
    return frames


def ahash(frame: bytes, size: int = 32) -> int:
    block = size // 8
    cells: list[float] = []
    for by in range(8):
        for bx in range(8):
            total = 0
            for y in range(by * block, (by + 1) * block):
                row_off = y * size
                for x in range(bx * block, (bx + 1) * block):
                    total += frame[row_off + x]
            cells.append(total / (block * block))
    mean = sum(cells) / len(cells)
    result = 0
    for i, v in enumerate(cells):
        if v >= mean:
            result |= 1 << i
    return result


def _luma_histogram(frame: bytes, bins: int = 16) -> list[float]:
    hist = [0] * bins
    for byte in frame:
        hist[min(byte * bins // 256, bins - 1)] += 1
    total = len(frame)
    return [h / total for h in hist]


def histogram_distance(a: bytes, b: bytes) -> float:
    ha = _luma_histogram(a)
    hb = _luma_histogram(b)
    l1 = sum(abs(x - y) for x, y in zip(ha, hb, strict=True))
    return l1 / 2.0


def _hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def score_uniqueness(
    src_path: str,
    variant_path: str,
    *,
    n_frames: int = 10,
    target: float | None = None,
) -> dict:
    base = {
        "uniqueness": None,
        "uniqueness_status": "unknown",
        "uniqueness_metric": METRIC_VERSION,
        "uniqueness_target": target,
    }
    try:
        src_frames = extract_gray_frames(src_path, n=n_frames)
        var_frames = extract_gray_frames(variant_path, n=n_frames)
        if not src_frames or not var_frames or len(src_frames) != len(var_frames):
            return base

        phash_dists: list[float] = []
        hist_dists: list[float] = []
        for sf, vf in zip(src_frames, var_frames, strict=True):
            phash_dists.append(_hamming(ahash(sf), ahash(vf)) / 64.0)
            hist_dists.append(histogram_distance(sf, vf))

        mean_phash = sum(phash_dists) / len(phash_dists)
        mean_hist = sum(hist_dists) / len(hist_dists)
        score = max(0.0, min(1.0, 0.7 * mean_phash + 0.3 * mean_hist))

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
        }
    except (OSError, subprocess.CalledProcessError, ValueError, TypeError):
        return base
