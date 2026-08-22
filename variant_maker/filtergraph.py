"""Phase 4. params -> (-vf, -af) strings. PURE (unit-tested; --dry-run prints).

Video filter ORDER is load-bearing:
  trim -> crop -> scale(even, range-aware) -> [rebuild round-trip] -> [±px resample
  fallback] -> [rotate w/ fill] -> [lenscorrection warp] -> eq(color) -> hue ->
  unsharp -> grain -> fps -> setpts(tempo) -> format=yuv420p
Audio mirrors time changes: atrim (identical) -> [pitch] -> atempo(=speed) ->
  equalizer -> loudnorm.

Trim supports an independent START (`trim_s`) and END (`trim_end_s`, a fingerprint
micro-trim off the tail); end trim needs the source duration (both builders take `src`)
since ffmpeg's `trim=end=` is an absolute timestamp, not an offset from the tail. Both
streams mirror the identical trim window, keeping video/audio in sync. Crop punch-in
also carries an x/y offset fraction (fingerprint axis; 0.5/0.5 == centered). The resize
uses color.even_scale_filter (the safe even form); color.zscale_convert_filter only fires
if the output target ever differs from the carried source tags. NEVER let a naive scale
reinterpret color range. Fast uniqueness is a reconstructive rebuild (down to
`rebuild_scale` then back to the platform canvas) — not a ±32 px peek.
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
# Sampler grain bands are calibrated on 1080×1920. ffmpeg noise is per-pixel.
# Linear short/1080 left the same on-screen grain on 720p (bigger pixels).
# Area (short/1080)² still read as "pretty decent grain" on a phone — 720p
# pixels are 1.5× larger, so area-18 looks like 1080 chroma ~27. Exponent
# 2.5 is the phone-viewing fix (720p chroma 40 → 15). Never go above the
# 1080 calibration (4K downscales stay 1.0).
_GRAIN_REF_SHORT_EDGE = 1080
_GRAIN_SIZE_EXPONENT = 2.5
# 720×1280 → 80×142. Strength is calibrated at this grid, not 1080 grain.
_CHROMA_CLOUD_FACTOR = 9
# Live SaveInta 6–10 + sigma=2 still read as chroma on the face. Cap the
# leftover 18–22 (and the loud 8–10 copies) so they cannot redraw snow.
_CHROMA_CLOUD_STRENGTH_MAX = 7
_CHROMA_CLOUD_BLUR = 4.0
# 720 talking-head luma dust. Cap leftover 14–20 (`softdust815a` c0s 15–17
# read as a little much). Luma-only — alls= would restack chroma snow.
_LUMA_DUST_MAX = 12
# Fixed EQ band centre frequencies by band count (data, not logic).
_EQ_BANDS = {1: (1000.0,), 2: (200.0, 4000.0)}


def grain_scale_for_size(width: int | None, height: int | None) -> float:
    """Phone-viewing scale vs 1080p short edge. Capped at 1 so we never add glitter."""
    if not width or not height:
        return 1.0
    try:
        short = min(int(width), int(height))
    except (TypeError, ValueError):
        return 1.0
    if short <= 0:
        return 1.0
    linear = min(short / _GRAIN_REF_SHORT_EDGE, 1.0)
    return linear ** _GRAIN_SIZE_EXPONENT


def apply_canvas_grain(grain: float, width: int | None, height: int | None) -> int:
    """1080-calibrated grain → integer ffmpeg noise strength on this pixel grid."""
    g = float(grain or 0.0)
    if g <= 0:
        return 0
    return max(1, round(g * grain_scale_for_size(width, height)))


def apply_chroma_cloud_strength(cloud: float) -> int:
    """Clamp the 720 overlay so leftover 18–22 / 8–10 params cannot redraw snow."""
    g = float(cloud or 0.0)
    if g <= 0:
        return 0
    return max(1, min(round(g), _CHROMA_CLOUD_STRENGTH_MAX))


def apply_luma_dust_strength(dust: float) -> int:
    """Clamp 720 luma dust. Leftover 14–20 cannot redraw the grainy pack."""
    g = float(dust or 0.0)
    if g <= 0:
        return 0
    return max(1, min(round(g), _LUMA_DUST_MAX))


def chroma_cloud_size(width: int, height: int, factor: int = _CHROMA_CLOUD_FACTOR) -> tuple[int, int]:
    """Even low-res grid for the chroma overlay (720×1280 → 80×142)."""
    w = max(int(width), 2)
    h = max(int(height), 2)
    fac = max(int(factor), 1)
    return max((w // fac) // 2 * 2, 2), max((h // fac) // 2 * 2, 2)


def chroma_cloud_applies(v: dict, width: int | None, height: int | None) -> bool:
    """True when the 720 talking-head overlay will actually be drawn.

    Sampler still emits phone-safe grain + chroma_cloud together (no extra RNG).
    Drawing both is the snow Jeff rejected — cloud replaces full-res chroma on
    canvases shorter than 1080. 1080 talking-head keeps the 34–42 recipe.
    """
    cloud = float(v.get("chroma_cloud") or 0.0)
    if cloud <= _EPS or not width or not height:
        return False
    try:
        return min(int(width), int(height)) < _GRAIN_REF_SHORT_EDGE
    except (TypeError, ValueError):
        return False


def _luma_dust_filter(strength: int, seed: object = None) -> str:
    """Luma-only temporal dust. c1s/c2s stay 0 so this is not stacked chroma."""
    noise = f"noise=c0s={strength}:c0f=t+u:c1s=0:c2s=0"
    if seed is not None:
        s = int(seed) & 0x7FFFFFFF
        noise += f":c0_seed={s}"
    return noise


def _chroma_cloud_graph(strength: int, width: int, height: int, seed: object = None) -> str:
    """Chroma-only overlay: generate noise at 1/9 size, blend onto Cb/Cr, leave luma."""
    lw, lh = chroma_cloud_size(width, height)
    noise = f"noise=c0s=0:c1s={strength}:c2s={strength}:c1f=u:c2f=u"
    if seed is not None:
        s = int(seed) & 0x7FFFFFFF
        noise += f":c1_seed={s}:c2_seed={s}"
    blur = f"gblur=sigma={_CHROMA_CLOUD_BLUR:g}"
    return (
        f"split[main][s];"
        f"[s]format=yuv444p,geq=lum='128':cb='128':cr='128',"
        f"scale={lw}:{lh},{noise},"
        f"scale={width}:{height}:flags=bicubic,{blur}[cl];"
        f"[main][cl]blend=c0_expr='A':c1_expr='A+B-128':c2_expr='A+B-128'"
    )


def _noise_filter(v: dict, width: int | None = None, height: int | None = None) -> str:
    """ffmpeg noise. Talking-head chroma-only keeps VMAF (luma) while SSIM All still moves."""
    g = apply_canvas_grain(v.get("grain") or 0.0, width, height)
    if v.get("noise_chroma"):
        noise = f"noise=c0s=0:c0f=u:c1s={g}:c1f=u:c2s={g}:c2f=u"
        ns = v.get("noise_seed")
        if ns is not None:
            s = int(ns) & 0x7FFFFFFF
            noise += f":c1_seed={s}:c2_seed={s}"
        return noise
    return f"noise=alls={g}:allf=t+u"


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


def even_rebuild_size(target_w: int, target_h: int, scale: float) -> tuple[int, int]:
    """Even intermediate size for a reconstructive down-then-up.

    Height follows AR. Never returns the identity size when ``scale`` is not ~1.
    """
    tw, th = int(target_w), int(target_h)
    s = float(scale)
    if tw <= 0 or th <= 0 or abs(s - 1.0) < _EPS or s <= 0:
        return tw, th
    w = max(round(tw * s) // 2 * 2, 2)
    h = max(round(w * th / tw) // 2 * 2, 2)
    if w == tw and h == th:
        w = max(tw - 2 if s < 1.0 else tw + 2, 2)
        h = max(round(w * th / tw) // 2 * 2, 2)
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
    # Talking-head chroma grain on the source grid (before platform scale).
    # Skip when the 720 chroma cloud will draw — stacking c1s 12–15 + cloud
    # 18–22 is the snow on lab pack 650f28dfb1f2.
    ow = platform.width or src.width
    oh = platform.height or src.height
    if (
        v.get("grain", 0.0) > _EPS
        and v.get("noise_chroma")
        and not chroma_cloud_applies(v, ow, oh)
    ):
        parts.append(_noise_filter(v, src.width, src.height))
    if platform.width and platform.height:
        parts.append(even_scale_filter(platform.width, platform.height))
        flags = _resample_flags(v.get("resample_flags"))
        rebuild = float(v.get("rebuild_scale") or 1.0)
        if abs(rebuild - 1.0) >= _EPS:
            rw, rh = even_rebuild_size(platform.width, platform.height, rebuild)
            if (rw, rh) != (platform.width, platform.height):
                parts.append(f"scale={rw}:{rh}:flags={flags}")
                parts.append(f"scale={platform.width}:{platform.height}:flags={flags}")
        else:
            px = int(v.get("resample_px") or 0)
            if px != 0:
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
    if v.get("grain", 0.0) > _EPS and not v.get("noise_chroma"):
        # Motion luma grain sits on the output canvas (after scale).
        ow = platform.width or src.width
        oh = platform.height or src.height
        parts.append(_noise_filter(v, ow, oh))
    # Phase 9: HQ + RIFE owns fps/tempo; skip ffmpeg drop/dupe so audio atempo still matches.
    if not v.get("defer_tempo"):
        if platform.fps:
            parts.append(f"fps={platform.fps:g}")
        speed = v.get("speed", 1.0)
        if abs(speed - 1.0) > _EPS:
            parts.append(f"setpts={1.0 / speed:.6f}*PTS")

    ow = platform.width or src.width
    oh = platform.height or src.height
    if chroma_cloud_applies(v, ow, oh):
        graph = _chroma_cloud_graph(
            apply_chroma_cloud_strength(float(v.get("chroma_cloud") or 0.0)),
            int(ow),
            int(oh),
            v.get("noise_seed"),
        )
        dust = apply_luma_dust_strength(float(v.get("luma_dust") or 0.0))
        if dust:
            graph = f"{graph},{_luma_dust_filter(dust, v.get('noise_seed'))}"
        return f"{','.join(parts)},{graph},format=yuv420p"

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
