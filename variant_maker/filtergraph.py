"""STUB — Phase 4. params -> (-vf, -af) strings. PURE (unit-tested; --dry-run prints).

Video filter ORDER is load-bearing:
  trim -> crop -> scale(even, range-aware) -> [rotate w/ fill+crop] ->
  eq(color) -> hue -> unsharp -> grain -> fps -> setpts(tempo) -> format=yuv420p
Audio mirrors time changes: atrim (identical) -> [pitch] -> atempo(=speed) ->
  equalizer -> [noise bed] -> loudnorm.

Use color.even_scale_filter / color.zscale_convert_filter for the scale step.
NEVER let a naive scale reinterpret color range.
"""
from __future__ import annotations

from .probe import SourceInfo
from .platforms import Platform


def build_video_filters(params: dict, src: SourceInfo, platform: Platform) -> str:
    raise NotImplementedError("Phase 4: assemble -vf in the documented order")


def build_audio_filters(params: dict, has_audio: bool) -> str:
    raise NotImplementedError("Phase 4: assemble -af; atempo must match video speed")
