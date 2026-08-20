"""Phase 4. params -> (-vf, -af) strings. PURE (unit-tested; --dry-run prints).

Video filter ORDER is load-bearing:
  trim -> crop -> scale(even, range-aware) -> [seeded resample] -> [rotate w/ fill] ->
  [lenscorrection warp] -> eq(color) -> hue -> unsharp -> grain -> fps -> setpts(tempo)
  -> format=yuv420p
Audio mirrors time changes: atrim (identical) -> [pitch] -> atempo(=speed) ->
  equalizer -> loudnorm.

Trim supports an independent START (`trim_s`) and END (`trim_end_s`, a fingerprint
micro-trim off the tail); end trim needs the source duration (both builders take `src`)
since ffmpeg's `trim=end=` is an absolute timestamp, not an offset from the tail. Both
streams mirror the identical trim window, keeping video/audio in sync. Crop punch-in
also carries an x/y offset fraction (fingerprint axis; 0.5/0.5 == centered). The resize
uses color.even_scale_filter (the safe even form); color.zscale_convert_filter only fires
if the output target ever differs from the carried source tags. NEVER let a naive scale
reinterpret color range.
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
from .sampler import clamp_trims

_EPS = 1e-6
_ROTATE_MIN_DEG = 0.05  # below this, rotation is a visual no-op that only risks a black sliver
_WARP_MIN = 1e-4
_RESAMPLE_FLAGS = frozenset({"lanczos", "spline", "bicubic"})
# ffmpeg's loudnorm (EBU R128) emits NaN/+-Inf on very short clips; AAC then fails.
# Skip loudnorm when post-trim, post-atempo audio would be shorter than this.
_LOUDNORM_MIN_S = 3.0
# Fixed EQ band centre frequencies by band count (data, not logic).
_EQ_BANDS = {1: (1000.0,), 2: (200.0, 4000.0)}


def _remaining_duration_s(v: dict, duration_s: float) -> float:
    """Wall-clock seconds left after start/end trim (before speed change)."""
    start_s, end_s = clamp_trims(v.get("trim_s", 0.0), v.get("trim_end_s", 0.0), duration_s)
    return max(0.0, duration_s - start_s - end_s)


def _trim_expr(v: dict, duration_s: float) -> str:
    """Build the `trim=...` (video) / caller prefixes `a` for `atrim=...` (audio) expr.

    Start trim (`trim_s`) and end trim (`trim_end_s`, a fingerprint micro-trim off the
    tail) are independent axes; end trim needs the source duration since ffmpeg's `trim`
    end is an absolute timestamp, not an offset from the end. Combined trims are scaled
    via clamp_trims so a short source cannot emit end <= start.
    """
    start_s, end_s = clamp_trims(v.get("trim_s", 0.0), v.get("trim_end_s", 0.0), duration_s)
    has_start = start_s > _EPS
    has_end = end_s > _EPS
    if not has_start and not has_end:
        return ""
    if has_start and has_end:
        return f"trim=start={start_s:.3f}:end={duration_s - end_s:.3f}"
    if has_start:
        return f"trim=start={start_s:.3f}"
    return f"trim=end={duration_s - end_s:.3f}"


def even_resample_size(target_w: int, target_h: int, px: int) -> tuple[int, int]:
    """Even intermediate size: ``target_w + px`` (even), height follows AR, even.

    Never returns the identity size when ``px != 0``.
    """
    tw, th = int(target_w), int(target_h)
    if px == 0 or tw <= 0 or th <= 0:
        return tw, th
    w = (tw + int(px)) // 2 * 2
    if w < 2:
        w = 2
    h = int(round(w * th / tw)) // 2 * 2
    if h < 2:
        h = 2
    if w == tw and h == th:
        w = tw + (-2 if px < 0 else 2)
        if w < 2:
            w = 2
        h = int(round(w * th / tw)) // 2 * 2
        if h < 2:
            h = 2
    return w, h


def _resample_flags(raw: object) -> str:
    s = str(raw or "lanczos")
    return s if s in _RESAMPLE_FLAGS else "lanczos"


def build_video_filters(params: dict, src: SourceInfo, platform: Platform) -> str:
    v = params["video"]
    out = resolve_output_color(src.color)
    parts: list[str] = []

    # trim (start and/or end; reset PTS so downstream filters see t=0). End trim needs the
    # source duration (fingerprint axis, drawn independently of trim_s in the sampler).
    trim_expr = _trim_expr(v, src.duration_s)
    if trim_expr:
        parts.append(f"{trim_expr},setpts=PTS-STARTPTS")

    # crop punch-in with an x/y offset fraction (fingerprint axis); the scale below
    # restores even dims. Offset 0.5/0.5 == the old centered crop.
    crop_keep = v.get("crop_keep", 1.0)
    if crop_keep < 1.0 - _EPS:
        crop_x = v.get("crop_x_frac", 0.5)
        crop_y = v.get("crop_y_frac", 0.5)
        parts.append(
            f"crop=iw*{crop_keep:.4f}:ih*{crop_keep:.4f}:"
            f"(iw-iw*{crop_keep:.4f})*{crop_x:.4f}:(ih-ih*{crop_keep:.4f})*{crop_y:.4f}"
        )

    # scale: range-aware conversion only when the target differs from source, then even resize
    if needs_conversion(src.color, out):
        conv = zscale_convert_filter(out)
        if conv:
            parts.append(conv)
    if platform.width and platform.height:
        parts.append(even_scale_filter(platform.width, platform.height))
        px = int(v.get("resample_px") or 0)
        if px != 0:
            flags = _resample_flags(v.get("resample_flags"))
            rw, rh = even_resample_size(platform.width, platform.height, px)
            parts.append(f"scale={rw}:{rh}:flags={flags}")
            parts.append(f"scale={platform.width}:{platform.height}:flags={flags}")

    # rotation (tiny angles; corner fill — proper inscribed-crop is a later refinement)
    if abs(v.get("rotate_deg", 0.0)) >= _ROTATE_MIN_DEG:
        parts.append(f"rotate={math.radians(v['rotate_deg']):.6f}:fillcolor=black")

    warp = float(v.get("warp_k1") or 0.0)
    if abs(warp) >= _WARP_MIN:
        parts.append(f"lenscorrection=cx=0.5:cy=0.5:k1={warp:.6f}:k2=0")

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
        parts.append(f"noise=alls={round(v['grain'])}:allf=t+u")
    # Phase 9: HQ + RIFE owns fps/tempo; skip ffmpeg drop/dupe so audio atempo still matches.
    if not v.get("defer_tempo"):
        if platform.fps:
            parts.append(f"fps={platform.fps:g}")
        speed = v.get("speed", 1.0)
        if abs(speed - 1.0) > _EPS:
            parts.append(f"setpts={1.0 / speed:.6f}*PTS")

    parts.append("format=yuv420p")
    return ",".join(parts)


def build_audio_filters(params: dict, src: SourceInfo, has_audio: bool) -> str:
    if not has_audio:
        return ""
    v = params["video"]
    a = params["audio"]
    parts: list[str] = []

    # identical trim to video (sync); "a" prefix mirrors trim/setpts -> atrim/asetpts
    trim_expr = _trim_expr(v, src.duration_s)
    if trim_expr:
        parts.append(f"a{trim_expr},asetpts=PTS-STARTPTS")

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

    # loudnorm after atempo — effective length is remaining/speed. Short clips
    # make loudnorm emit NaN which AAC rejects (exit 234).
    speed = max(a.get("speed", 1.0), _EPS)
    effective_s = _remaining_duration_s(v, src.duration_s) / speed
    if effective_s >= _LOUDNORM_MIN_S:
        parts.append(f"loudnorm=I={a['loudnorm_i']:.1f}:TP=-1.5:LRA=11")
    return ",".join(parts)
