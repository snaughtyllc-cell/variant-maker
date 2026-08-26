"""Look-first visual gate. Runs on the *actual* output, not the VMAF proxy.

VMAF `quality_render` strips fingerprint ops (crop, shade, …) so frames align.
Uniqueness SSIM *wants* difference. Lab pack `lookaqmtp` scored VMAF 97–99 and
33–34 bits and still looked like lava on the face. This metric is coarse luma
MAE at 16×28 — the scale of cookie / lighting overlays.

Calibration 2026-08-25 (16×28, 8-bit MAE):

| Pair | MAE |
|---|---|
| Identity | 0 |
| AQMTp signed medium | 12–32 |
| SaveInta signed medium | 20–32 |
| lookaqmtp shade 100 (8×14, gblur 10) | 41–57 |

Gate **38**. One blotchy sample fails. Missing files / ffmpeg errors →
`unknown` (do not block uniqueness). Log: `docs/ops/look-learnings.md`.
"""
from __future__ import annotations

import os
import subprocess

from . import uniqueness

LOOK_METRIC = "coarse_luma_v1"
LOOK_GRID = (16, 28)
# 8-bit mean absolute error on the coarse grid. Signed 720 medium landed ≤32;
# rejected shade was ≥41. Do not raise this to "pass" a blotchy overlay.
LOOK_LUMA_MAX = 38.0
FRAME_FRACS = uniqueness.FRAME_FRACS
STILL_WIDTH = 360


def look_src_name(index: int) -> str:
    return f"look_v{int(index):02d}_src.jpg"


def look_var_name(index: int) -> str:
    return f"look_v{int(index):02d}.jpg"


def _probe_duration(path: str) -> float:
    return uniqueness._probe_duration(path)


def _coarse_luma_mae(path_a: str, t_a: float, path_b: str, t_b: float) -> float:
    """8-bit MAE of luma after area-scale to LOOK_GRID. 0 = identical."""
    gw, gh = LOOK_GRID
    vf = (
        f"[0:v]scale={gw}:{gh}:flags=area,format=gray[a];"
        f"[1:v]scale={gw}:{gh}:flags=area,format=gray[b];"
        f"[a][b]blend=all_mode=difference,format=gray,scale=1:1:flags=area,format=gray"
    )
    proc = subprocess.run(
        [
            "ffmpeg", "-v", "error",
            "-ss", f"{max(0.0, t_a):.6f}", "-i", path_a,
            "-ss", f"{max(0.0, t_b):.6f}", "-i", path_b,
            "-filter_complex", vf,
            "-frames:v", "1",
            "-f", "rawvideo", "pipe:1",
        ],
        check=True,
        capture_output=True,
    )
    if not proc.stdout:
        raise ValueError("empty coarse-luma pipe")
    return float(proc.stdout[0])


def _extract_jpeg(path: str, t: float, out_path: str) -> None:
    if os.path.exists(out_path):
        os.remove(out_path)
    subprocess.run(
        [
            "ffmpeg", "-v", "error",
            "-ss", f"{max(0.0, t):.6f}", "-i", path,
            "-frames:v", "1",
            "-vf", f"scale={STILL_WIDTH}:-2",
            "-q:v", "3",
            "-y", out_path,
        ],
        check=True,
        capture_output=True,
    )
    if not os.path.isfile(out_path) or os.path.getsize(out_path) <= 0:
        raise ValueError(f"empty look still {out_path}")


def write_look_stills(
    src_path: str, variant_path: str, out_dir: str, index: int,
) -> dict[str, str]:
    """Mid-frame source vs variant JPEGs for Studio / CLI. Returns basenames."""
    os.makedirs(out_dir, exist_ok=True)
    src_name = look_src_name(index)
    var_name = look_var_name(index)
    src_jpg = os.path.join(out_dir, src_name)
    var_jpg = os.path.join(out_dir, var_name)
    dur_a = max(_probe_duration(src_path), 0.1)
    dur_b = max(_probe_duration(variant_path), 0.1)
    t = 0.5
    _extract_jpeg(src_path, t * dur_a, src_jpg)
    _extract_jpeg(variant_path, t * dur_b, var_jpg)
    return {"look_src": src_name, "look_var": var_name}


def score_look(src_path: str, variant_path: str) -> dict:
    """Look gate on the real files. Never uses the VMAF quality proxy."""
    base = {
        "look_status": "unknown",
        "look_metric": LOOK_METRIC,
        "look_mae": None,
        "look_mae_max": None,
        "look_target": LOOK_LUMA_MAX,
    }
    try:
        dur_a = max(_probe_duration(src_path), 0.1)
        dur_b = max(_probe_duration(variant_path), 0.1)
        maes: list[float] = []
        for frac in FRAME_FRACS:
            maes.append(_coarse_luma_mae(src_path, frac * dur_a, variant_path, frac * dur_b))
        mean_mae = sum(maes) / len(maes)
        max_mae = max(maes)
        passed = max_mae <= LOOK_LUMA_MAX
        return {
            "look_status": "ok" if passed else "fail",
            "look_metric": LOOK_METRIC,
            "look_mae": round(mean_mae, 2),
            "look_mae_max": round(max_mae, 2),
            "look_target": LOOK_LUMA_MAX,
        }
    except (OSError, ValueError, subprocess.CalledProcessError, IndexError):
        return base
