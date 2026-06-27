"""Color correctness — the actual fix for the washed-out / '1990s phone' look.

The wash-out is almost never a missing AI feature. It's a color-tagging / range bug:
re-encoding while dropping or mismatching range (tv/limited vs pc/full) or primaries/
transfer/matrix (bt709 for HD) makes the player misinterpret pixels -> flat, desaturated.

Strategy:
  1. Probe source tags (probe.ColorTags).
  2. Resolve the intended OUTPUT tags (carry source; default unknowns to HD bt709/tv).
  3. Convert range-aware via zscale when source/output differ.
  4. ALWAYS tag the output explicitly so players don't guess.
"""
from __future__ import annotations

from .probe import ColorTags

# HD default. SD (<= 576p) would use bt601 — extend resolve_output_color if you need it.
BT709 = ColorTags(range="tv", primaries="bt709", transfer="bt709", matrix="bt709")


def resolve_output_color(src: ColorTags) -> ColorTags:
    """Carry known source tags; fill unknowns with HD bt709/tv defaults."""
    return ColorTags(
        range=src.range or BT709.range,
        primaries=src.primaries or BT709.primaries,
        transfer=src.transfer or BT709.transfer,
        matrix=src.matrix or BT709.matrix,
    )


def needs_conversion(src: ColorTags, out: ColorTags) -> bool:
    """True if any *known* source tag differs from the output target."""
    pairs = [
        (src.range, out.range),
        (src.primaries, out.primaries),
        (src.transfer, out.transfer),
        (src.matrix, out.matrix),
    ]
    return any(s is not None and s != o for s, o in pairs)


def even_scale_filter(width: int, height: int) -> str:
    """Scale to target, forcing EVEN dimensions (libx264 requirement).

    Uses -2 so the encoder can't be handed an odd dimension regardless of source AR.
    """
    return f"scale={width}:{height}:force_original_aspect_ratio=disable,scale=trunc(iw/2)*2:trunc(ih/2)*2"


def zscale_convert_filter(out: ColorTags) -> str:
    """Range-aware colorspace conversion. Use INSTEAD of a naive scale when converting.

    zscale understands range; a plain `scale` will silently reinterpret it (the bug).
    """
    parts = []
    if out.matrix:
        parts.append(f"matrix={out.matrix}")
    if out.transfer:
        parts.append(f"transfer={out.transfer}")
    if out.primaries:
        parts.append(f"primaries={out.primaries}")
    if out.range:
        parts.append(f"range={'full' if out.range == 'pc' else 'limited'}")
    return "zscale=" + ":".join(parts) if parts else ""


def output_color_args(out: ColorTags) -> list[str]:
    """ffmpeg OUTPUT flags that explicitly tag the encoded stream. ALWAYS emit these."""
    args: list[str] = []
    if out.matrix:
        args += ["-colorspace", out.matrix]
    if out.primaries:
        args += ["-color_primaries", out.primaries]
    if out.transfer:
        args += ["-color_trc", out.transfer]
    if out.range:
        args += ["-color_range", out.range]
    return args
