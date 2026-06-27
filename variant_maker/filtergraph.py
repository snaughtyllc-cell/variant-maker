"""Phase 4. params -> (-vf, -af) strings. PURE (unit-tested; --dry-run prints).

Video filter ORDER is load-bearing:
  trim -> crop -> scale(even, range-aware) -> [rotate w/ fill+crop] ->
  eq(color) -> hue -> unsharp -> grain -> fps -> setpts(tempo) -> format=yuv420p
Audio mirrors time changes: atrim (identical) -> [pitch] -> atempo(=speed) ->
  equalizer -> loudnorm.

Trim is applied from the START (start-trim mirrors cleanly to audio without needing the
source duration, keeping the two streams in sync). The resize uses color.even_scale_filter
(the safe even form); color.zscale_convert_filter only fires if the output target ever
differs from the carried source tags. NEVER let a naive scale reinterpret color range.
"""
from __future__ import annotations

import math

from .color import (
    even_scale_filter,
    needs_conversion,
    resolve_output_color,
    zscale_convert_filter,
)
from .platforms import Platform
from .probe import SourceInfo

_EPS = 1e-6
_ROTATE_MIN_DEG = 0.05  # below this, rotation is a visual no-op that only risks a black sliver
# Fixed EQ band centre frequencies by band count (data, not logic).
_EQ_BANDS = {1: (1000.0,), 2: (200.0, 4000.0)}


def build_video_filters(params: dict, src: SourceInfo, platform: Platform) -> str:
    v = params["video"]
    out = resolve_output_color(src.color)
    parts: list[str] = []

    # trim (from start; reset PTS so downstream filters see t=0)
    if v.get("trim_s", 0.0) > _EPS:
        parts.append(f"trim=start={v['trim_s']:.3f},setpts=PTS-STARTPTS")

    # crop punch-in (centered); the scale below restores even dims
    crop_keep = v.get("crop_keep", 1.0)
    if crop_keep < 1.0 - _EPS:
        parts.append(f"crop=iw*{crop_keep:.4f}:ih*{crop_keep:.4f}")

    # scale: range-aware conversion only when the target differs from source, then even resize
    if needs_conversion(src.color, out):
        conv = zscale_convert_filter(out)
        if conv:
            parts.append(conv)
    if platform.width and platform.height:
        parts.append(even_scale_filter(platform.width, platform.height))

    # rotation (tiny angles; corner fill — proper inscribed-crop is a later refinement)
    if abs(v.get("rotate_deg", 0.0)) >= _ROTATE_MIN_DEG:
        parts.append(f"rotate={math.radians(v['rotate_deg']):.6f}:fillcolor=black")

    # color (always emitted — this is the color stage)
    parts.append(
        f"eq=brightness={v['brightness']:.4f}:contrast={v['contrast']:.4f}:"
        f"saturation={v['saturation']:.4f}:gamma={v['gamma']:.4f}"
    )

    if abs(v.get("hue_deg", 0.0)) > _EPS:
        parts.append(f"hue=h={v['hue_deg']:.4f}")
    if v.get("unsharp", 0.0) > _EPS:
        parts.append(f"unsharp=5:5:{v['unsharp']:.4f}:5:5:0.0")
    if v.get("grain", 0.0) > _EPS:
        parts.append(f"noise=alls={int(round(v['grain']))}:allf=t+u")
    if platform.fps:
        parts.append(f"fps={platform.fps:g}")

    # tempo (one speed factor; audio mirrors it via atempo)
    speed = v.get("speed", 1.0)
    if abs(speed - 1.0) > _EPS:
        parts.append(f"setpts={1.0 / speed:.6f}*PTS")

    parts.append("format=yuv420p")
    return ",".join(parts)


def build_audio_filters(params: dict, has_audio: bool) -> str:
    if not has_audio:
        return ""
    v = params["video"]
    a = params["audio"]
    parts: list[str] = []

    # identical trim to video (sync)
    if v.get("trim_s", 0.0) > _EPS:
        parts.append(f"atrim=start={v['trim_s']:.3f},asetpts=PTS-STARTPTS")

    # pitch only when rubberband produced a non-zero shift
    pitch = a.get("pitch_pct", 0.0)
    if abs(pitch) > _EPS:
        parts.append(f"rubberband=pitch={1.0 + pitch / 100.0:.6f}")

    # one speed factor on both streams — atempo MUST equal video speed
    parts.append(f"atempo={a['speed']:.6f}")

    gains = a.get("eq_gains", [])
    freqs = _EQ_BANDS.get(a.get("eq_bands", len(gains)), ())
    for freq, gain in zip(freqs, gains):
        parts.append(f"equalizer=f={freq:g}:width_type=o:width=1:g={gain:.3f}")

    parts.append(f"loudnorm=I={a['loudnorm_i']:.1f}:TP=-1.5:LRA=11")
    return ",".join(parts)
