"""Phase 5. Build + run one ffmpeg invocation per variant.

Applies color.output_color_args(...) on OUTPUT, -map_metadata -1, -map_chapters -1,
demuxer + encoder +bitexact, libx264 (fast/medium, never slow on daily Fast) with
sampled crf/gop/bframes/refs, always AAC+aresample when audio exists, and a social
maxrate ceiling (constrained VBR — CRF still picks quality). Drops H.264 SEI
(NAL type 6) so the x264 version/options string is not a constant. Returns the exact
command string for the manifest (the reproduction contract — x264 isn't
bit-deterministic, so the cmd + params ARE the record).
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

# H.264 SEI NAL is type 6 (includes x264's unregistered user-data "x264 - core …").
# x264-params info=0 does not drop that SEI on current ffmpeg/libx264.
H264_DROP_SEI_BSF = "filter_units=remove_types=6"


def h264_drop_sei_args() -> list[str]:
    """PURE: drop H.264 SEI after libx264 so the version string is not in the file."""
    return ["-bsf:v", H264_DROP_SEI_BSF]


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
    encode_preset = str(v.get("encode_preset") or "medium")
    if encode_preset not in ("fast", "medium"):
        encode_preset = "medium"
    crf = v.get("encode_crf", v["crf"])
    bf = int(v.get("encode_bf") or 3)
    refs = int(v.get("encode_refs") or 3)
    x264 = f"info=0:repeat-headers=1:bframes={bf}:ref={refs}"
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-i", src.path,
        "-map_metadata", "-1",
        "-map_chapters", "-1",
        "-fflags", "+bitexact",
        "-flags", "+bitexact",
        video_flag, vf,
        "-c:v", "libx264", "-preset", encode_preset,
        "-crf", str(crf), "-g", str(v["gop"]),
        "-x264-params", x264,
        *x264_rate_args(platform),
        "-pix_fmt", "yuv420p",
        *output_color_args(out_color),
        "-movflags", "+faststart",
        "-metadata", "encoder=",
        *h264_drop_sei_args(),
    ]
    if src.has_audio:
        af = build_audio_filters(params, src, True)
        kbps = int(a.get("aac_kbps") or 160)
        if not af:
            rate = int(a.get("aresample_hz") or 48000)
            if rate not in (44100, 48000):
                rate = 48000
            af = f"aresample={rate}"
        cmd += ["-af", af, "-c:a", "aac", "-b:a", f"{kbps}k"]
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
