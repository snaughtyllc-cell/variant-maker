"""STUB — Phase 6. In-loop quality guard. Fail -> reduce strength & regenerate.

histogram_sanity(src, variant) -> bool   # always on, cheap; catches wash-out / crush
vmaf(src, variant, params) -> float      # stronger; compute on the QUALITY RENDER
  (quality-affecting ops only, at source geometry/timing) because libvmaf needs
  frame-aligned, same-resolution ref & distorted — you CANNOT vmaf across trim/tempo/fps.
"""
from __future__ import annotations


def histogram_sanity(src_path: str, variant_path: str, tol: float = 0.06) -> bool:
    raise NotImplementedError("Phase 6: compare luma+saturation histograms vs source")


def vmaf(src_path: str, quality_render_path: str) -> float:
    raise NotImplementedError("Phase 6: libvmaf on the geometry/time-matched quality render")
