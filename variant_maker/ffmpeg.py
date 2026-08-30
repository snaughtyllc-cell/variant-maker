"""Phase 5. Build + run one ffmpeg invocation per variant.

Applies color.output_color_args(...) on OUTPUT, -map_metadata -1, -fflags +bitexact,
libx264 with sampled crf/gop, aac audio, and a social maxrate ceiling (constrained
VBR — CRF still picks quality). Returns the exact command string for the manifest
(the reproduction contract — x264 isn't bit-deterministic, so the cmd + params ARE the record).
"""
from __future__ import annotations

import random
import shlex
import subprocess

from .color import output_color_args, resolve_output_color
from .filtergraph import build_audio_filters, build_video_filters
from .platforms import Platform, x264_rate_args
from .probe import SourceInfo

# None = not probed yet. Cached so has_rubberband() does not spawn ffmpeg per variant.
_rubberband_cached: bool | None = None


def has_rubberband() -> bool:
    """True when this ffmpeg build exposes the rubberband audio filter.

    Never raises: missing ffmpeg, a failed listing, or a listing without the
    filter all return False. Result is cached at module level.
    """
    global _rubberband_cached
    if _rubberband_cached is not None:
        return _rubberband_cached
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        _rubberband_cached = False
        return False
    if result.returncode != 0:
        _rubberband_cached = False
        return False
    listing = result.stdout or ""
    _rubberband_cached = any(
        "rubberband" in line.split() for line in listing.splitlines()
    )
    return _rubberband_cached


# Optional file tags after source metadata is stripped. Seeded so the same
# variant reprints the same city / phone / clock.
_US_CITIES = (
    (40.7128, -74.0060),
    (34.0522, -118.2437),
    (41.8781, -87.6298),
    (29.7604, -95.3698),
    (33.4484, -112.0740),
    (39.9526, -75.1652),
    (32.7767, -96.7970),
    (37.7749, -122.4194),
)
_US_MODELS = ("iPhone 13 Pro", "iPhone 14 Pro", "iPhone 15 Pro", "iPhone 15")


def us_metadata_args(seed: int) -> list[str]:
    """PURE: Apple + US location + creation_time argv pairs."""
    rng = random.Random(int(seed) ^ 0x5553)
    lat, lon = rng.choice(_US_CITIES)
    model = rng.choice(_US_MODELS)
    loc = f"{lat:+08.4f}{lon:+09.4f}/"
    year = rng.randint(2023, 2026)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    hour = rng.randint(8, 21)
    minute = rng.randint(0, 59)
    second = rng.randint(0, 59)
    created = f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}Z"
    pairs = (
        ("make", "Apple"),
        ("model", model),
        ("com.apple.quicktime.make", "Apple"),
        ("com.apple.quicktime.model", model),
        ("location", loc),
        ("location-eng", loc),
        ("creation_time", created),
    )
    out: list[str] = []
    for key, value in pairs:
        out.extend(["-metadata", f"{key}={value}"])
    return out


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise subprocess.CalledProcessError(
            result.returncode, result.args, output=result.stdout, stderr=detail or result.stderr,
        )
    return result


def build_render_cmd(src: SourceInfo, params: dict, platform: Platform, out_path: str) -> list[str]:
    """PURE: assemble the full ffmpeg argv for one variant (unit-tested without ffmpeg)."""
    v = params["video"]
    a = params["audio"]
    out_color = resolve_output_color(src.color)

    vf = build_video_filters(params, src, platform)
    video_flag = "-filter_complex" if ";" in vf else "-vf"
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-i", src.path,
        "-map_metadata", "-1",
        "-fflags", "+bitexact",
        video_flag, vf,
        "-c:v", "libx264", "-preset", "medium",
        "-crf", str(v["crf"]), "-g", str(v["gop"]),
        *x264_rate_args(platform),
        "-pix_fmt", "yuv420p",
        *output_color_args(out_color),
    ]
    if src.has_audio:
        af = build_audio_filters(params, src, True)
        if af:
            cmd += ["-af", af, "-c:a", "aac", "-b:a", f"{a['aac_kbps']}k"]
        else:
            cmd += ["-c:a", "copy"]
    else:
        cmd += ["-an"]
    if params.get("us_metadata"):
        seed = v.get("us_metadata_seed")
        if seed is None:
            seed = v.get("noise_seed") or v.get("gop") or 0
        cmd += us_metadata_args(int(seed))
    cmd += [out_path]
    return cmd


def render_variant(
    src: SourceInfo, params: dict, platform: Platform, out_path: str, *, dry_run: bool = False
) -> tuple[str, str]:
    """Build the command, render the variant (unless dry_run), return (out_path, cmd_str)."""
    cmd = build_render_cmd(src, params, platform, out_path)
    cmd_str = shlex.join(cmd)
    if not dry_run:
        run(cmd)
    return out_path, cmd_str
