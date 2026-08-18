"""Phase 8 (hero op). Downscale -> Real-ESRGAN upscale.

Invents clean, plausible detail: output is sharp AND statistically distinct (new pixels).
Tool: realesrgan-ncnn-vulkan (image-sequence based, runs on the Mac GPU via Vulkan).
Operates on a lossless PNG frame round-trip. Lazy/optional — Tier 1 runs without it.

Locate the binary via $VARIANT_MAKER_REALESRGAN_DIR (default ./models/realesrgan) or PATH.
"""
from __future__ import annotations

import copy
import os
import shlex
import shutil
import subprocess
import tempfile

from .backends import (  # noqa: F401 — DEFAULT_*/NATIVE_SCALE re-exported for back-compat
    DEFAULT_DIR,
    DEFAULT_MODEL,
    NATIVE_SCALE,
    NcnnVulkanBackend,
    get_backend,
    native_scale,
)


def available(model_dir: str = DEFAULT_DIR) -> bool:
    """True only if the resolved upscale backend can actually run here (gate Tier-2 on this).

    Honors $VARIANT_MAKER_UPSCALE_BACKEND, so on a Linux GPU box this reflects CUDA
    availability; on the Mac (default) it's the ncnn binary + models check.
    """
    return get_backend(model_dir=model_dir).available()


def build_upscale_cmd(
    in_dir: str, out_dir: str, *, scale: int = 4, model: str = DEFAULT_MODEL,
    model_dir: str = DEFAULT_DIR, fmt: str = "png",
) -> list[str]:
    """PURE ncnn argv (back-compat shim; new code uses a backend's .argv/.command_str)."""
    return NcnnVulkanBackend(model_dir).argv(in_dir, out_dir, scale=scale, model=model, fmt=fmt)


def upscale_dir(in_dir: str, out_dir: str, *, scale: int = 4, model: str = DEFAULT_MODEL,
                model_dir: str = DEFAULT_DIR, fmt: str = "png") -> str:
    """Upscale every frame in in_dir -> out_dir via the ncnn backend. Returns out_dir."""
    return NcnnVulkanBackend(model_dir).upscale_dir(in_dir, out_dir, scale=scale, model=model,
                                                    fmt=fmt)


def _even(n: float) -> int:
    return int(n) // 2 * 2


def upscale_clip(
    src, params: dict, out_path: str, *, platform, scale: int | None = None,
    model: str = DEFAULT_MODEL, model_dir: str = DEFAULT_DIR, backend=None,
) -> tuple[str, str, list]:
    """Hero op: full Tier-1 render at a downscaled target -> AI-upscale its frames ->
    reassemble at the target geometry, re-muxing the (already correct) audio.

    All color/sync/trim/speed correctness comes from the tested `render_variant`; the audio
    is COPIED from that render so it can't desync. The upscale step is the only OS/GPU-specific
    part — it goes through `backend` (ncnn on mac, CUDA on a Linux GPU box). Returns
    (out_path, cmd_str, neural_ops).
    """
    from .. import ffmpeg
    from ..color import output_color_args, resolve_output_color
    from ..platforms import Platform

    if backend is None:
        backend = get_backend(model_dir=model_dir)
    if scale is None:
        scale = native_scale(model)  # native ratio — non-native -s corrupts into tiles

    tw = _even(platform.width or src.width)
    th = _even(platform.height or src.height)
    dw, dh = _even(tw / scale), _even(th / scale)
    fps = platform.fps or src.fps

    work = tempfile.mkdtemp(prefix="vm_neural_")
    small = os.path.join(work, "small.mp4")
    in_dir = os.path.join(work, "in")
    up_dir = os.path.join(work, "up")
    os.makedirs(in_dir)
    cmds: list[str] = []
    interp_ops: list = []
    try:
        from . import interpolate as rife

        # Stage A — complete Tier-1 variant at the downscaled target (all filters + audio).
        # When RIFE will retime, skip ffmpeg fps=/speed setpts so we don't drop/dupe first.
        render_params = params
        use_rife = rife.available() and rife.needed(params, src, platform)
        if use_rife:
            render_params = copy.deepcopy(params)
            render_params["video"]["defer_tempo"] = True
        _, cmd_a = ffmpeg.render_variant(src, render_params, Platform("neural-pre", dw, dh, fps), small)
        cmds.append(cmd_a)

        # Stage B — lossless frames out, optional RIFE retime, then AI-upscale.
        extract = ["ffmpeg", "-y", "-v", "error", "-i", small, os.path.join(in_dir, "f%06d.png")]
        subprocess.run(extract, check=True, capture_output=True)
        cmds.append(shlex.join(extract))
        upscale_in = in_dir
        if use_rife:
            n_in = sum(1 for n in os.listdir(in_dir) if n.lower().endswith(".png"))
            speed = float(params["video"]["speed"])
            n_out = rife.target_frame_count(n_in, src.fps, fps, speed)
            if n_out != n_in:
                rife_dir = os.path.join(work, "rife")
                rife.interpolate_dir(in_dir, rife_dir, n_frames=n_out)
                cmds.append(rife.command_str(in_dir, rife_dir, n_frames=n_out))
                upscale_in = rife_dir
                interp_ops.append({
                    "op": "interpolate", "model": rife.DEFAULT_MODEL,
                    "n_in": n_in, "n_out": n_out,
                })
        backend.upscale_dir(upscale_in, up_dir, scale=scale, model=model)
        cmds.append(backend.command_str(upscale_in, up_dir, scale=scale, model=model))

        # Real-ESRGAN mutes saturation (~9%, isolated by stage). Measure the upscaled result
        # and apply a single eq correction so the FINAL output's saturation matches source —
        # measured (not a fixed constant), since several stages each shave a bit.
        from .. import quality
        frames = os.path.join(up_dir, "f%06d.png")
        scale_fmt = f"scale={tw}:{th}:flags=lanczos,format=yuv420p"
        probe_mp4 = os.path.join(work, "probe.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-framerate", f"{fps:g}", "-i", frames,
             "-vf", scale_fmt, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", probe_mp4],
            check=True, capture_output=True,
        )
        target_sat = quality._signalstats(src.path)[1]
        cur_sat = quality._signalstats(probe_mp4)[1]
        ratio = max(0.5, min(2.0, target_sat / cur_sat)) if cur_sat else 1.0
        sat_fix = f"eq=saturation={ratio:.4f}," if abs(ratio - 1.0) > 1e-3 else ""

        # Stage C — reassemble at target geometry; restore saturation; copy audio; tag color.
        oc = resolve_output_color(src.color)
        reassemble = ["ffmpeg", "-y", "-v", "error", "-framerate", f"{fps:g}", "-i", frames]
        if src.has_audio:
            reassemble += ["-i", small, "-map", "0:v:0", "-map", "1:a:0"]
        reassemble += ["-vf", f"{sat_fix}{scale_fmt}",
                       "-c:v", "libx264", "-preset", "medium", "-crf", str(params["video"]["crf"]),
                       "-pix_fmt", "yuv420p", *output_color_args(oc)]
        if src.has_audio:
            reassemble += ["-c:a", "copy", "-shortest"]
        reassemble += [out_path]
        subprocess.run(reassemble, check=True, capture_output=True)
        cmds.append(shlex.join(reassemble))

        # Spatial-corruption guard: VMAF of this hq output (downscaled) vs the clean
        # PRE-upscale render `small`. Computed HERE because `small` is ephemeral. The
        # histogram+VMAF guard never runs through the upscaler, so it can't see tile-seam
        # garble; this can. Measured before cleanup wipes the pre-upscale reference.
        spatial_vmaf = round(quality.spatial_coherence(out_path, small), 2)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    neural_ops = interp_ops + [{"op": "upscale", "model": model, "scale": scale,
                   "from": f"{dw}x{dh}", "to": f"{tw}x{th}", "sat_match": round(ratio, 4),
                   "spatial_vmaf": spatial_vmaf}]
    return out_path, " && ".join(cmds), neural_ops
