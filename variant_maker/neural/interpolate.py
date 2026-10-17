"""Phase 9. RIFE frame interpolation for clean retiming.

Synthesize in-between frames for speed/fps instead of ffmpeg drop/dupe (`fps=` + `setpts`).
Default tool: rife-ncnn-vulkan. Lazy/optional — Fast and HQ-without-RIFE stay on ffmpeg tempo.

Locate the binary via $VARIANT_MAKER_RIFE_DIR (default ./models/rife) or PATH.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess

DEFAULT_DIR = os.environ.get("VARIANT_MAKER_RIFE_DIR", "models/rife")
DEFAULT_MODEL = "rife-v4.6"
_EPS = 1e-3


def _binary(model_dir: str) -> str | None:
    local = os.path.join(model_dir, "rife-ncnn-vulkan")
    if os.path.exists(local):
        return local
    return shutil.which("rife-ncnn-vulkan")


def available(model_dir: str = DEFAULT_DIR) -> bool:
    """True only if the RIFE binary and a models directory can actually run here."""
    if _binary(model_dir) is None:
        return False
    return os.path.isdir(os.path.join(model_dir, "models")) or os.path.isdir(
        os.path.join(model_dir, DEFAULT_MODEL)
    )


def needed(params: dict, src, platform) -> bool:
    """True when ffmpeg would resample time (speed or fps change)."""
    speed = float(params.get("video", {}).get("speed", 1.0))
    if abs(speed - 1.0) > _EPS:
        return True
    dst = platform.fps if platform is not None else None
    return bool(dst and src is not None and abs(float(dst) - float(src.fps)) > 0.05)


def target_frame_count(n_in: int, src_fps: float, dst_fps: float, speed: float) -> int:
    """Output frames so duration_out = (n_in / src_fps) / speed at dst_fps."""
    src_fps = max(src_fps, _EPS)
    speed = max(speed, _EPS)
    dst_fps = dst_fps if dst_fps and dst_fps > 0 else src_fps
    n = round(n_in / src_fps / speed * dst_fps)
    return max(1, n)


def build_interpolate_cmd(
    in_dir: str, out_dir: str, *, n_frames: int,
    model: str = DEFAULT_MODEL, model_dir: str = DEFAULT_DIR,
) -> list[str]:
    """PURE rife-ncnn-vulkan argv (unit-tested, no GPU). `-n` is the target frame count."""
    model_path = os.path.join(model_dir, "models", model)
    if not os.path.isdir(model_path):
        model_path = os.path.join(model_dir, model)
    return [
        _binary(model_dir) or "rife-ncnn-vulkan",
        "-i", in_dir, "-o", out_dir,
        "-n", str(int(n_frames)),
        "-m", model_path,
    ]


def interpolate_dir(
    in_dir: str, out_dir: str, *, n_frames: int,
    model: str = DEFAULT_MODEL, model_dir: str = DEFAULT_DIR,
) -> str:
    """Retime the PNG sequence in in_dir -> out_dir with target n_frames. Returns out_dir."""
    os.makedirs(out_dir, exist_ok=True)
    cmd = build_interpolate_cmd(in_dir, out_dir, n_frames=n_frames, model=model, model_dir=model_dir)
    subprocess.run(cmd, check=True, capture_output=True)
    return out_dir


def command_str(
    in_dir: str, out_dir: str, *, n_frames: int,
    model: str = DEFAULT_MODEL, model_dir: str = DEFAULT_DIR,
) -> str:
    return shlex.join(build_interpolate_cmd(
        in_dir, out_dir, n_frames=n_frames, model=model, model_dir=model_dir,
    ))
