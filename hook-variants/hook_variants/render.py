"""Burn one ASS overlay and extract a look still. ffmpeg only."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hook_variants.ass import ass_sha256, build_ass
from hook_variants.types import HookParams, StylePreset, VideoInfo


@dataclass(frozen=True)
class RenderResult:
    mp4: Path
    still: Path
    ass: Path
    cmd: list[str]
    ass_sha256: str = ""


def escape_filter_path(path: str | Path) -> str:
    """Escape ``\\``, ``:``, and ``'`` for an ffmpeg filter argument."""
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def write_manifest(path: str | Path, payload: Any) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def _run_ffmpeg(cmd: list[str]) -> None:
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg is not installed or not on PATH") from exc
    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"ffmpeg failed ({completed.returncode}): {err}")


def _variant_paths(
    *,
    video: Path,
    hook: HookParams,
    out_dir: Path | None,
    out_mp4: Path | None,
    out_still: Path | None,
    out_ass: Path | None,
) -> tuple[Path, Path, Path]:
    if out_mp4 is not None and out_still is not None and out_ass is not None:
        return Path(out_mp4), Path(out_still), Path(out_ass)
    if out_dir is None:
        raise ValueError("render_variant requires out_dir or out_mp4/out_still/out_ass")
    dest = Path(out_dir)
    dest.mkdir(parents=True, exist_ok=True)
    stem = f"{video.stem}_h{hook.index:02d}"
    return dest / f"{stem}.mp4", dest / f"{stem}.jpg", dest / f"{stem}.ass"


def render_variant(
    video: Path | str | None = None,
    hook: HookParams | None = None,
    style: StylePreset | None = None,
    info: VideoInfo | None = None,
    out_dir: Path | str | None = None,
    *,
    fonts_dir: Path | str,
    out_mp4: Path | str | None = None,
    out_still: Path | str | None = None,
    out_ass: Path | str | None = None,
) -> RenderResult:
    """Write ASS, burn it in last, then extract one JPEG still."""
    if video is None or hook is None or style is None or info is None:
        raise TypeError("render_variant requires video, hook, style, and info")

    src = Path(video)
    mp4, still, ass_path = _variant_paths(
        video=src,
        hook=hook,
        out_dir=Path(out_dir) if out_dir is not None else None,
        out_mp4=Path(out_mp4) if out_mp4 is not None else None,
        out_still=Path(out_still) if out_still is not None else None,
        out_ass=Path(out_ass) if out_ass is not None else None,
    )
    for target in (mp4, still, ass_path):
        target.parent.mkdir(parents=True, exist_ok=True)

    script = build_ass(hook, style, info.width, info.height, info.duration_s)
    ass_path.write_text(script, encoding="utf-8")
    digest = ass_sha256(script)

    fonts = Path(fonts_dir)
    vf = (
        f"ass={escape_filter_path(ass_path.resolve())}"
        f":fontsdir={escape_filter_path(fonts.resolve())}"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "veryfast",
        "-crf",
        "18",
    ]
    if info.has_audio:
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    else:
        cmd += ["-an"]
    cmd += ["-movflags", "+faststart", str(mp4)]
    _run_ffmpeg(cmd)

    still_at = min(1.0, max(0.0, info.duration_s / 2.0))
    still_cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{still_at:.3f}",
        "-i",
        str(mp4),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(still),
    ]
    _run_ffmpeg(still_cmd)

    return RenderResult(
        mp4=mp4,
        still=still,
        ass=ass_path,
        cmd=cmd,
        ass_sha256=digest,
    )
