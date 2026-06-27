"""Phase 6. In-loop quality guard. Fail -> reduce strength & regenerate.

histogram_sanity(src, variant) -> bool   # always on, cheap; catches wash-out / crush
vmaf(src, variant, params) -> float      # stronger; compute on the QUALITY RENDER
  (quality-affecting ops only, at source geometry/timing) because libvmaf needs
  frame-aligned, same-resolution ref & distorted — you CANNOT vmaf across trim/tempo/fps.
"""
from __future__ import annotations

import json
import subprocess

from . import ffmpeg
from .platforms import get_platform
from .probe import SourceInfo

# Geometric/temporal axes are neutralized in the quality proxy: VMAF needs frame-aligned,
# same-resolution ref & distorted, so only the quality-affecting ops (color/sharpen/grain/
# encode) survive — at source geometry and timing.
_QUALITY_NEUTRAL = {"crop_keep": 1.0, "rotate_deg": 0.0, "trim_s": 0.0, "speed": 1.0}


def _signalstats(path: str) -> tuple[float, float]:
    """Mean (YAVG luma, SATAVG saturation) across frames via the signalstats lavfi graph."""
    cmd = [
        "ffprobe", "-v", "error", "-f", "lavfi",
        "-i", f"movie={path},signalstats",
        "-show_entries", "frame_tags=lavfi.signalstats.YAVG,lavfi.signalstats.SATAVG",
        "-print_format", "json",
    ]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True)
    frames = json.loads(out.stdout).get("frames", [])
    ys, ss = [], []
    for f in frames:
        tags = f.get("tags", {})
        if "lavfi.signalstats.YAVG" in tags:
            ys.append(float(tags["lavfi.signalstats.YAVG"]))
        if "lavfi.signalstats.SATAVG" in tags:
            ss.append(float(tags["lavfi.signalstats.SATAVG"]))
    yavg = sum(ys) / len(ys) if ys else 0.0
    satavg = sum(ss) / len(ss) if ss else 0.0
    return yavg, satavg


def histogram_sanity(src_path: str, variant_path: str, tol: float = 0.06) -> bool:
    """True if the variant's luma + saturation haven't collapsed/shifted beyond `tol`.

    Cheap, always-on guard for the gross failures — wash-out (saturation collapse),
    crushed blacks / blown highlights (luma shift). Not a fidelity metric; VMAF on the
    quality render is the stronger check.
    """
    src_y, src_s = _signalstats(src_path)
    var_y, var_s = _signalstats(variant_path)

    def rel(a: float, b: float) -> float:
        return abs(b - a) / a if a else 0.0

    return rel(src_y, var_y) <= tol and rel(src_s, var_s) <= tol


def quality_render(src: SourceInfo, params: dict, out_path: str) -> str:
    """Render the quality proxy: quality ops only, at source geometry/timing (for VMAF)."""
    v = dict(params["video"])
    v.update(_QUALITY_NEUTRAL)
    qparams = {"video": v, "audio": params["audio"]}
    ffmpeg.render_variant(src, qparams, get_platform("none"), out_path)
    return out_path


def passes_guard(
    src_path: str, variant_path: str, quality_render_path: str, *, floor: float = 90.0,
    tol: float = 0.06,
) -> dict:
    """Combined guard decision: histogram sanity on the variant + VMAF on the quality render."""
    hist_ok = histogram_sanity(src_path, variant_path, tol)
    score = vmaf(src_path, quality_render_path)
    return {"vmaf": score, "histogram_ok": hist_ok, "passed": bool(hist_ok and score >= floor)}


def regen_until_pass(attempt, *, max_regen: int = 3, strength: float = 1.0, falloff: float = 0.6) -> dict:
    """Reject -> reduce strength -> regenerate, bounded by max_regen.

    `attempt(strength) -> dict` samples + renders + guards one variant and returns its guard
    result (must include 'passed'). On failure, strength is scaled by `falloff` and retried.
    Returns the first passing result, else the best-effort last attempt; tags 'regen_count'.
    """
    result = attempt(strength)
    regen = 0
    while not result["passed"] and regen < max_regen:
        regen += 1
        strength *= falloff
        result = attempt(strength)
    return {**result, "regen_count": regen}


def vmaf(src_path: str, quality_render_path: str) -> float:
    """libvmaf score (0..100) of the quality render vs source. Both MUST be frame-aligned
    and the same resolution — that's what `quality_render` guarantees."""
    log_path = quality_render_path + ".vmaf.json"
    cmd = [
        "ffmpeg", "-hide_banner", "-v", "error",
        "-i", quality_render_path, "-i", src_path,
        "-lavfi", f"[0:v][1:v]libvmaf=log_fmt=json:log_path={log_path}",
        "-f", "null", "-",
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    with open(log_path) as f:
        data = json.load(f)
    pooled = data.get("pooled_metrics", {}).get("vmaf")
    if pooled:
        return float(pooled["mean"])
    frames = data.get("frames", [])
    vals = [fr["metrics"]["vmaf"] for fr in frames if "vmaf" in fr.get("metrics", {})]
    return sum(vals) / len(vals) if vals else 0.0
