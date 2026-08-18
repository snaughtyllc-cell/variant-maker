"""Source inspection: ffprobe metadata (including color tags) + content hash.

Color tags are first-class here because dropping/mismatching them on re-encode is the
#1 cause of the washed-out look. We probe them so color.py can carry them correctly.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class ColorTags:
    range: str | None        # "tv" (limited) | "pc" (full) | None
    primaries: str | None    # e.g. "bt709"
    transfer: str | None     # e.g. "bt709"
    matrix: str | None       # e.g. "bt709"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SourceInfo:
    path: str
    sha256: str
    duration_s: float
    width: int
    height: int
    fps: float
    has_audio: bool
    color: ColorTags

    def to_dict(self) -> dict:
        d = asdict(self)
        d["color"] = self.color.to_dict()
        return d


def sha256_file(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _parse_fps(rate: str | None) -> float:
    """ffprobe gives fps as a fraction string like '30000/1001'."""
    if not rate or rate == "0/0":
        return 0.0
    if "/" in rate:
        num, den = rate.split("/", 1)
        den_f = float(den)
        return float(num) / den_f if den_f else 0.0
    return float(rate)


def _parse_ffprobe(data: dict, path: str, sha: str) -> SourceInfo:
    """Pure: turn ffprobe JSON into SourceInfo. Unit-tested without ffmpeg."""
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    fmt = data.get("format", {})
    duration = float(video.get("duration") or fmt.get("duration") or 0.0)

    def _norm(v: str | None) -> str | None:
        if v in (None, "", "unknown", "und"):
            return None
        return v

    color = ColorTags(
        range=_norm(video.get("color_range")),
        primaries=_norm(video.get("color_primaries")),
        transfer=_norm(video.get("color_transfer")),
        matrix=_norm(video.get("color_space")),
    )

    return SourceInfo(
        path=path,
        sha256=sha,
        duration_s=duration,
        width=int(video.get("width") or 0),
        height=int(video.get("height") or 0),
        fps=_parse_fps(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        has_audio=has_audio,
        color=color,
    )


def probe(path: str, *, hash_content: bool = True) -> SourceInfo:
    """Run ffprobe and return SourceInfo. Requires ffprobe on PATH.

    Set hash_content=False for ingest decisions (width/HDR). Hashing a 4K
    iPhone file just to see if it needs a 1080 proxy is wasted I/O.
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-print_format", "json",
        "-show_format", "-show_streams",
        path,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(out.stdout)
    sha = sha256_file(path) if hash_content else ""
    return _parse_ffprobe(data, path, sha)
