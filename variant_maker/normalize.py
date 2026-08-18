"""Normalize uploads so quality/uniqueness gates see a stable SDR source.

iPhone 4K/HEVC is the common Studio case. Platforms are 1080×1920, so a long-edge
> 1920 source is proxied to ≤1920 in the same encode as any HDR/10-bit → 8-bit
H.264 pass. That shrinks R2 + RunPod work. It does not shrink the phone→Studio
upload — the file has already arrived.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .color import BT709, output_color_args, resolve_output_color
from .probe import SourceInfo, probe

# Matches reels/tiktok/shorts long edge. 1080×1920 and 1920×1080 stay as-is.
MAX_LONG_EDGE = 1920
_HDR_TRANSFERS = ("smpte2084", "arib-std-b67", "bt2020")


def _even(n: int) -> int:
    return max(2, n - (n % 2))


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


def is_hdr_or_10bit(pix_fmt: str = "", color_transfer: str = "") -> bool:
    """True for 10-bit / HDR / Dolby Vision sources that break hist+VMAF loops."""
    pix = (pix_fmt or "").lower()
    transfer = (color_transfer or "").lower()
    if "10" in pix or "12" in pix or "p010" in pix:
        return True
    return any(t in transfer for t in _HDR_TRANSFERS)


def needs_sdr_normalize(path: str) -> bool:
    """True for 10-bit / HDR / Dolby Vision sources that break hist+VMAF loops."""
    try:
        pix = _ffprobe_field(path, "pix_fmt")
        transfer = _ffprobe_field(path, "color_transfer")
    except (OSError, subprocess.CalledProcessError):
        return False
    return is_hdr_or_10bit(pix, transfer)


def needs_size_proxy(width: int, height: int, max_long: int = MAX_LONG_EDGE) -> bool:
    """True when the coded long edge is bigger than the platform target."""
    return max(int(width or 0), int(height or 0)) > max_long


def proxy_output_size(
    width: int, height: int, max_long: int = MAX_LONG_EDGE,
) -> tuple[int, int]:
    """Fit inside max_long, keep AR, force even dims (libx264)."""
    w, h = int(width or 0), int(height or 0)
    if w <= 0 or h <= 0:
        return 2, 2
    long_edge = max(w, h)
    if long_edge <= max_long:
        return _even(w), _even(h)
    scale = max_long / long_edge
    return _even(round(w * scale)), _even(round(h * scale))


def proxy_scale_filter(width: int, height: int) -> str:
    """Explicit even scale. Geometry only — not a color conversion."""
    w, h = proxy_output_size(width, height)
    return f"scale={w}:{h}:flags=lanczos,scale=trunc(iw/2)*2:trunc(ih/2)*2"


def needs_upload_proxy(info: SourceInfo, *, pix_fmt: str = "") -> bool:
    """True when ingest should rewrite the file (HDR/10-bit and/or oversized)."""
    transfer = info.color.transfer or ""
    return needs_size_proxy(info.width, info.height) or is_hdr_or_10bit(pix_fmt, transfer)


def _proxy_vf(info: SourceInfo, *, hdr: bool) -> str:
    parts: list[str] = []
    if hdr:
        # Linearize + hable, then tag as HD. Same encode as the size proxy.
        parts.append(
            "zscale=t=linear:npl=100,tonemap=hable,"
            "zscale=p=bt709:t=bt709:m=bt709:r=limited"
        )
    if needs_size_proxy(info.width, info.height):
        parts.append(proxy_scale_filter(info.width, info.height))
    parts.append("format=yuv420p")
    return ",".join(parts)


def proxy_upload(src: str | Path, dest: str | Path, info: SourceInfo | None = None) -> Path:
    """One H.264 8-bit encode: optional HDR→SDR + optional long-edge ≤ 1920."""
    src_path = Path(src)
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    meta = info if info is not None else probe(str(src_path))
    pix = ""
    try:
        pix = _ffprobe_field(str(src_path), "pix_fmt")
    except (OSError, subprocess.CalledProcessError):
        pix = ""
    hdr = is_hdr_or_10bit(pix, meta.color.transfer or "")
    out_color = BT709 if hdr else resolve_output_color(meta.color)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-v", "error",
        "-i", str(src_path),
        "-vf", _proxy_vf(meta, hdr=hdr),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        *output_color_args(out_color),
    ]
    if meta.has_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]
    cmd.append(str(dest_path))
    subprocess.run(cmd, check=True, capture_output=True)
    return dest_path


def normalize_to_sdr(src_path: str, dst_path: str) -> str:
    """Write an 8-bit yuv420p H.264 proxy. Returns dst_path."""
    return str(proxy_upload(src_path, dst_path))


def maybe_normalize_upload(path: str) -> str:
    """If HDR/10-bit or oversized, replace with a 1080-class H.264 proxy."""
    try:
        info = probe(path)
        pix = _ffprobe_field(path, "pix_fmt")
    except (OSError, subprocess.CalledProcessError, ValueError):
        return path
    if not needs_upload_proxy(info, pix_fmt=pix):
        return path
    root, _ext = os.path.splitext(path)
    dst = f"{root}_proxy.mp4"
    proxy_upload(path, dst, info)
    if os.path.abspath(dst) != os.path.abspath(path):
        try:
            os.remove(path)
        except OSError:
            pass
    return dst
