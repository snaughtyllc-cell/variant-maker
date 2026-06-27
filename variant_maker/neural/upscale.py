"""STUB — Phase 8 (hero op). Downscale -> Real-ESRGAN upscale.

Invents clean, plausible detail: output is sharp AND statistically distinct (new pixels).
Default tool: realesrgan-ncnn-vulkan (broad GPU support, image-sequence based).
Operates on a lossless frame round-trip (scratch/). Watch temporal flicker.
"""
def upscale_frames(*args, **kwargs):
    raise NotImplementedError("Phase 8: downscale then Real-ESRGAN upscale frame sequence")
