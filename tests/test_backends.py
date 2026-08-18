"""Upscaler backend seam: one interface, two implementations.

NcnnVulkanBackend (mac, the verified path) and CudaRealEsrganBackend (Linux GPU). Only the
locally-knowable parts are tested here — interface, argv/command construction, model-name
mapping, availability gating, selection. Actual CUDA inference is a deploy-time smoke test on
real NVIDIA hardware (can't run on this Mac).
"""
import pytest

from variant_maker.neural import backends


def test_native_scale_known_for_default_model():
    assert backends.native_scale("realesrgan-x4plus") == 4
    assert backends.native_scale("unknown-model") == 4  # safe default (4x models are the norm)


# ---- ncnn (mac) -------------------------------------------------------------

def test_ncnn_argv_matches_realesrgan_cli():
    b = backends.NcnnVulkanBackend(model_dir="models/realesrgan")
    cmd = b.argv("in/", "out/", scale=4, model="realesrgan-x4plus")
    assert cmd[cmd.index("-i") + 1] == "in/"
    assert cmd[cmd.index("-o") + 1] == "out/"
    assert cmd[cmd.index("-s") + 1] == "4"
    assert cmd[cmd.index("-n") + 1] == "realesrgan-x4plus"
    assert cmd[cmd.index("-m") + 1].endswith("models")


def test_ncnn_available_false_for_bogus_dir():
    assert backends.NcnnVulkanBackend("/nonexistent/realesrgan").available() is False


def test_ncnn_is_an_upscale_backend():
    assert isinstance(backends.NcnnVulkanBackend("x"), backends.UpscaleBackend)


# ---- cuda (Linux GPU) -------------------------------------------------------

def test_cuda_maps_ncnn_model_name_to_pytorch():
    b = backends.CudaRealEsrganBackend()
    argv = b.argv("in/", "out/", scale=4, model="realesrgan-x4plus")
    assert "RealESRGAN_x4plus" in argv          # ncnn name -> pytorch weight name
    assert "realesrgan-x4plus" not in argv


def test_cuda_argv_carries_io_and_scale():
    b = backends.CudaRealEsrganBackend()
    argv = b.argv("in/", "out/", scale=4, model="realesrgan-x4plus")
    assert argv[argv.index("-i") + 1] == "in/"
    assert argv[argv.index("-o") + 1] == "out/"
    assert argv[argv.index("-s") + 1] == "4"


def test_cuda_unmapped_model_passes_through():
    b = backends.CudaRealEsrganBackend()
    argv = b.argv("in/", "out/", scale=4, model="some-custom-x4")
    assert "some-custom-x4" in argv


def test_cuda_not_available_without_cuda():
    # this Mac has no NVIDIA/CUDA (and likely no torch) -> must gate to False, never crash
    assert backends.CudaRealEsrganBackend().available() is False


def test_cuda_is_an_upscale_backend():
    assert isinstance(backends.CudaRealEsrganBackend(), backends.UpscaleBackend)


# ---- selection --------------------------------------------------------------

def test_get_backend_defaults_to_ncnn(monkeypatch):
    monkeypatch.delenv("VARIANT_MAKER_UPSCALE_BACKEND", raising=False)
    assert isinstance(backends.get_backend(model_dir="models/realesrgan"),
                      backends.NcnnVulkanBackend)


def test_get_backend_env_selects_cuda(monkeypatch):
    monkeypatch.setenv("VARIANT_MAKER_UPSCALE_BACKEND", "cuda")
    assert isinstance(backends.get_backend(), backends.CudaRealEsrganBackend)


def test_get_backend_explicit_arg_overrides_env(monkeypatch):
    monkeypatch.setenv("VARIANT_MAKER_UPSCALE_BACKEND", "cuda")
    assert isinstance(backends.get_backend("ncnn", model_dir="x"), backends.NcnnVulkanBackend)


def test_get_backend_unknown_raises():
    with pytest.raises(ValueError, match="backend"):
        backends.get_backend("nope")
