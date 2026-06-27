"""Phase 8 (hero op). Downscale -> Real-ESRGAN upscale.

Invents clean, plausible detail: output is sharp AND statistically distinct (new pixels).
Tool: realesrgan-ncnn-vulkan (image-sequence based, runs on the Mac GPU via Vulkan).
Operates on a lossless PNG frame round-trip. Lazy/optional — Tier 1 runs without it.

Locate the binary via $VARIANT_MAKER_REALESRGAN_DIR (default ./models/realesrgan) or PATH.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile

DEFAULT_DIR = os.environ.get("VARIANT_MAKER_REALESRGAN_DIR", "models/realesrgan")
DEFAULT_MODEL = "realesrgan-x4plus"  # photo model (NOT the anime default) — right for real footage
# Each model has a NATIVE scale; using a non-native -s (e.g. 2 with the 4x model) corrupts
# output into misaligned tile seams. Always upscale at the model's native ratio.
NATIVE_SCALE = {"realesrgan-x4plus": 4, "realesrgan-x4plus-anime": 4, "realesrnet-x4plus": 4}


def _binary(model_dir: str = DEFAULT_DIR) -> str | None:
    local = os.path.join(model_dir, "realesrgan-ncnn-vulkan")
    if os.path.exists(local):
        return local
    return shutil.which("realesrgan-ncnn-vulkan")


def available(model_dir: str = DEFAULT_DIR) -> bool:
    """True only if BOTH the binary and the models dir are present (gate Tier-2 on this).

    A binary-on-PATH with no models would pass a naive check and then fail at runtime.
    """
    return _binary(model_dir) is not None and os.path.isdir(os.path.join(model_dir, "models"))


def build_upscale_cmd(
    in_dir: str, out_dir: str, *, scale: int = 4, model: str = DEFAULT_MODEL,
    model_dir: str = DEFAULT_DIR, fmt: str = "png",
) -> list[str]:
    """PURE: argv to upscale an image-sequence directory (unit-tested without the binary)."""
    return [
        _binary(model_dir) or "realesrgan-ncnn-vulkan",
        "-i", in_dir, "-o", out_dir,
        "-s", str(scale), "-n", model,
        "-m", os.path.join(model_dir, "models"),
        "-f", fmt,
    ]


def upscale_dir(in_dir: str, out_dir: str, **kw) -> str:
    """Upscale every frame in in_dir -> out_dir via Real-ESRGAN. Returns out_dir."""
    os.makedirs(out_dir, exist_ok=True)
    subprocess.run(build_upscale_cmd(in_dir, out_dir, **kw), check=True, capture_output=True)
    return out_dir


def _even(n: float) -> int:
    return int(n) // 2 * 2


def upscale_clip(
    src, params: dict, out_path: str, *, platform, scale: int | None = None,
    model: str = DEFAULT_MODEL, model_dir: str = DEFAULT_DIR,
) -> tuple[str, str, list]:
    """Hero op: full Tier-1 render at a downscaled target -> AI-upscale its frames ->
    reassemble at the target geometry, re-muxing the (already correct) audio.

    All color/sync/trim/speed correctness comes from the tested `render_variant`; the audio
    is COPIED from that render so it can't desync. Returns (out_path, cmd_str, neural_ops).
    """
    from .. import ffmpeg
    from ..color import output_color_args, resolve_output_color
    from ..platforms import Platform

    if scale is None:
        scale = NATIVE_SCALE.get(model, 4)  # native ratio — non-native -s corrupts into tiles

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
    try:
        # Stage A — complete Tier-1 variant at the downscaled target (all filters + audio).
        _, cmd_a = ffmpeg.render_variant(src, params, Platform("neural-pre", dw, dh, fps), small)
        cmds.append(cmd_a)

        # Stage B — lossless frames out, AI-upscale them up.
        extract = ["ffmpeg", "-y", "-v", "error", "-i", small, os.path.join(in_dir, "f%06d.png")]
        subprocess.run(extract, check=True, capture_output=True)
        cmds.append(shlex.join(extract))
        upscale_dir(in_dir, up_dir, scale=scale, model=model, model_dir=model_dir)
        cmds.append(shlex.join(build_upscale_cmd(in_dir, up_dir, scale=scale, model=model,
                                                 model_dir=model_dir)))

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
    finally:
        shutil.rmtree(work, ignore_errors=True)

    neural_ops = [{"op": "upscale", "model": model, "scale": scale,
                   "from": f"{dw}x{dh}", "to": f"{tw}x{th}", "sat_match": round(ratio, 4)}]
    return out_path, " && ".join(cmds), neural_ops
