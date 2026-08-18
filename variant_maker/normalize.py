"""Normalize uploads so quality/uniqueness gates see a stable SDR source."""
from __future__ import annotations

import os
import subprocess


def _ffprobe_field(path: str, key: str) -> str:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", f"stream={key}",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return (out.stdout or "").strip()


def needs_sdr_normalize(path: str) -> bool:
    """True for 10-bit / HDR / Dolby Vision sources that break hist+VMAF loops."""
    try:
        pix = _ffprobe_field(path, "pix_fmt").lower()
        transfer = _ffprobe_field(path, "color_transfer").lower()
    except (OSError, subprocess.CalledProcessError):
        return False
    if "10" in pix or "12" in pix or "p010" in pix:
        return True
    if any(t in transfer for t in ("smpte2084", "arib-std-b67", "bt2020")):
        return True
    return False


def normalize_to_sdr(src_path: str, dst_path: str) -> str:
    """Write an 8-bit yuv420p H.264 proxy. Returns dst_path."""
    os.makedirs(os.path.dirname(dst_path) or ".", exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-v", "error",
        "-i", src_path,
        "-vf", "format=yuv420p",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        dst_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return dst_path


def maybe_normalize_upload(path: str) -> str:
    """If `path` is HDR/10-bit, replace it with an SDR sibling and return that path."""
    if not needs_sdr_normalize(path):
        return path
    root, ext = os.path.splitext(path)
    dst = f"{root}_sdr.mp4"
    normalize_to_sdr(path, dst)
    return dst
