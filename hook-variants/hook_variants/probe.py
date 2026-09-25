"""ffprobe → VideoInfo. No Lab / variant_maker imports."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from hook_variants.types import VideoInfo


def _parse_fps(rate: str | None) -> float:
    if not rate or rate == "0/0":
        return 0.0
    if "/" in rate:
        num, den = rate.split("/", 1)
        try:
            den_f = float(den)
            return float(num) / den_f if den_f else 0.0
        except ValueError:
            return 0.0
    try:
        return float(rate)
    except ValueError:
        return 0.0


def _rotation_deg(video: dict) -> float:
    tags = video.get("tags") if isinstance(video.get("tags"), dict) else {}
    raw = tags.get("rotate")
    if raw not in (None, "", "unknown"):
        try:
            return float(raw)
        except (TypeError, ValueError):
            pass
    for item in video.get("side_data_list") or []:
        if not isinstance(item, dict) or "rotation" not in item:
            continue
        try:
            return float(item["rotation"])
        except (TypeError, ValueError):
            continue
    return 0.0


def _display_size(width: int, height: int, rotation_deg: float) -> tuple[int, int]:
    turns = int(round(float(rotation_deg) / 90.0)) % 4
    if turns in (1, 3):
        return height, width
    return width, height


def _even(value: int) -> int:
    return int(value) - int(value) % 2


def probe(path: str | Path) -> VideoInfo:
    """Run ffprobe and return display-size :class:`VideoInfo`. Raise on failure."""
    src = str(path)
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        src,
    ]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(completed.stdout)
    except FileNotFoundError as exc:
        raise RuntimeError("ffprobe is not installed or not on PATH") from exc
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError) as exc:
        detail = ""
        if isinstance(exc, subprocess.CalledProcessError):
            detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(f"ffprobe failed for {src}: {detail or exc}") from exc

    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video:
        raise RuntimeError(f"no video stream in {src}")

    width, height = _display_size(
        int(video.get("width") or 0),
        int(video.get("height") or 0),
        _rotation_deg(video),
    )
    width, height = _even(width), _even(height)
    if width <= 0 or height <= 0:
        raise RuntimeError(f"invalid video size for {src}: {width}x{height}")

    fmt = data.get("format") or {}
    try:
        duration = float(video.get("duration") or fmt.get("duration") or 0.0)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"invalid duration for {src}") from exc

    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    return VideoInfo(
        path=src,
        width=width,
        height=height,
        duration_s=duration,
        fps=_parse_fps(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        has_audio=has_audio,
    )
