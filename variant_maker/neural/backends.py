"""Upscaler backend seam — the one platform-specific part of the neural tier.

`upscale_clip` is platform-agnostic ffmpeg/Python (render small -> extract frames -> upscale
the frame dir -> reassemble -> spatial guard). Only "upscale this image-sequence directory"
is GPU/OS-specific, so that's all a backend owns:

  - NcnnVulkanBackend   — mac (and any Vulkan box): the realesrgan-ncnn-vulkan binary. VERIFIED.
  - CudaRealEsrganBackend — Linux x86 + NVIDIA: PyTorch Real-ESRGAN. Command construction and
    gating are tested here; ACTUAL inference + output-frame naming are a deploy-time smoke
    test on real NVIDIA hardware (cannot run on this Mac — see WARNING on the class).

Select with `get_backend()` / the VARIANT_MAKER_UPSCALE_BACKEND env var.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from abc import ABC, abstractmethod

DEFAULT_DIR = os.environ.get("VARIANT_MAKER_REALESRGAN_DIR", "models/realesrgan")
DEFAULT_MODEL = "realesrgan-x4plus"  # photo model (NOT the anime default) — right for real footage
# Each model has a NATIVE scale; a non-native -s (e.g. 2 with a 4x model) corrupts output into
# misaligned tile seams. Always upscale at the model's native ratio.
NATIVE_SCALE = {"realesrgan-x4plus": 4, "realesrgan-x4plus-anime": 4, "realesrnet-x4plus": 4}

# ncnn model name -> the PyTorch Real-ESRGAN weight name the CUDA path loads.
_PYTORCH_MODEL = {
    "realesrgan-x4plus": "RealESRGAN_x4plus",
    "realesrgan-x4plus-anime": "RealESRGAN_x4plus_anime_6B",
    "realesrnet-x4plus": "RealESRNet_x4plus",
}


def native_scale(model: str) -> int:
    return NATIVE_SCALE.get(model, 4)


class UpscaleBackend(ABC):
    name = "base"

    @abstractmethod
    def available(self) -> bool:
        """True only if this backend can actually run here (gate Tier-2 on it)."""

    @abstractmethod
    def argv(self, in_dir: str, out_dir: str, *, scale: int, model: str,
             fmt: str = "png") -> list[str]:
        """PURE: the argv to upscale an image-sequence directory (unit-tested, no GPU)."""

    def command_str(self, in_dir: str, out_dir: str, *, scale: int, model: str,
                    fmt: str = "png") -> str:
        return shlex.join(self.argv(in_dir, out_dir, scale=scale, model=model, fmt=fmt))

    def upscale_dir(self, in_dir: str, out_dir: str, *, scale: int, model: str,
                    fmt: str = "png") -> str:
        """Upscale every frame in_dir -> out_dir. Contract: out_dir holds the upscaled frames
        in the SAME ordering/names so ffmpeg can reassemble the sequence."""
        os.makedirs(out_dir, exist_ok=True)
        subprocess.run(self.argv(in_dir, out_dir, scale=scale, model=model, fmt=fmt),
                       check=True, capture_output=True)
        return out_dir


class NcnnVulkanBackend(UpscaleBackend):
    """realesrgan-ncnn-vulkan (image-sequence, runs on the Mac GPU via Vulkan). The verified
    local path. Locate the binary via $VARIANT_MAKER_REALESRGAN_DIR (default ./models/realesrgan)
    or PATH; models live in <model_dir>/models."""

    name = "ncnn"

    def __init__(self, model_dir: str = DEFAULT_DIR):
        self.model_dir = model_dir

    def _binary(self) -> str | None:
        local = os.path.join(self.model_dir, "realesrgan-ncnn-vulkan")
        if os.path.exists(local):
            return local
        return shutil.which("realesrgan-ncnn-vulkan")

    def available(self) -> bool:
        # A binary-on-PATH with no models would pass a naive check then fail at runtime.
        return self._binary() is not None and os.path.isdir(os.path.join(self.model_dir, "models"))

    def argv(self, in_dir: str, out_dir: str, *, scale: int, model: str,
             fmt: str = "png") -> list[str]:
        return [
            self._binary() or "realesrgan-ncnn-vulkan",
            "-i", in_dir, "-o", out_dir,
            "-s", str(scale), "-n", model,
            "-m", os.path.join(self.model_dir, "models"),
            "-f", fmt,
        ]


class CudaRealEsrganBackend(UpscaleBackend):
    """PyTorch Real-ESRGAN on CUDA — the Linux x86 + NVIDIA production path (serverless GPU).

    WARNING: NOT runnable on this Mac (no NVIDIA/CUDA). What's tested here is command
    construction, model-name mapping, and that availability gates to False without CUDA. The
    same-names contract for `upscale_dir` is met by pointing `script` at the shipped
    name-preserving CLI (deploy/runpod/realesrgan_infer.py, set via $VARIANT_MAKER_REALESRGAN_PY
    in the worker image) instead of the official inference_realesrgan.py (whose `--suffix`
    renaming would break ffmpeg reassembly). The actual CUDA inference is still a DEPLOY-TIME
    smoke test — do not assume this path works until it has passed the spatial-corruption
    guard on real NVIDIA output.
    """

    name = "cuda"

    def __init__(self, *, python: str | None = None, script: str | None = None,
                 weights_dir: str | None = None):
        self.python = python or os.environ.get("VARIANT_MAKER_PYTHON", "python")
        self.script = script or os.environ.get("VARIANT_MAKER_REALESRGAN_PY",
                                               "inference_realesrgan.py")
        self.weights_dir = weights_dir or os.environ.get("VARIANT_MAKER_REALESRGAN_WEIGHTS")

    def available(self) -> bool:
        try:
            import torch
            return bool(torch.cuda.is_available())
        except Exception:
            return False

    def argv(self, in_dir: str, out_dir: str, *, scale: int, model: str,
             fmt: str = "png") -> list[str]:
        weight = _PYTORCH_MODEL.get(model, model)
        cmd = [self.python, self.script, "-n", weight, "-i", in_dir, "-o", out_dir,
               "-s", str(scale), "--fp32"]
        if self.weights_dir:
            cmd += ["--model_path", os.path.join(self.weights_dir, weight + ".pth")]
        return cmd


def get_backend(name: str | None = None, *, model_dir: str = DEFAULT_DIR) -> UpscaleBackend:
    """Resolve a backend: explicit `name` > $VARIANT_MAKER_UPSCALE_BACKEND > default 'ncnn'."""
    name = name or os.environ.get("VARIANT_MAKER_UPSCALE_BACKEND", "ncnn")
    if name == "ncnn":
        return NcnnVulkanBackend(model_dir)
    if name == "cuda":
        return CudaRealEsrganBackend()
    raise ValueError(f"unknown upscale backend {name!r}; choose 'ncnn' or 'cuda'")
