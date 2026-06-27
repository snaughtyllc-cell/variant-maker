import os
import subprocess

import pytest

from variant_maker.neural import upscale
from conftest import HAS_FFMPEG

MODEL_DIR = "models/realesrgan"
HAS_RESR = upscale.available(MODEL_DIR)


def test_build_upscale_cmd_flags():
    cmd = upscale.build_upscale_cmd("in/", "out/", scale=4, model="realesrgan-x4plus",
                                    model_dir=MODEL_DIR)
    assert cmd[cmd.index("-i") + 1] == "in/"
    assert cmd[cmd.index("-o") + 1] == "out/"
    assert cmd[cmd.index("-s") + 1] == "4"
    assert cmd[cmd.index("-n") + 1] == "realesrgan-x4plus"
    assert cmd[cmd.index("-m") + 1].endswith("models")


def test_available_is_false_for_bogus_dir():
    assert upscale.available("/nonexistent/realesrgan") is False


def test_available_is_false_when_models_missing(tmp_path):
    """Binary present but no models/ dir -> unusable; gating must not pass it."""
    binonly = tmp_path / "binonly"
    binonly.mkdir()
    (binonly / "realesrgan-ncnn-vulkan").write_text("")
    assert upscale.available(str(binonly)) is False


@pytest.mark.integration
@pytest.mark.skipif(not (HAS_FFMPEG and HAS_RESR), reason="needs ffmpeg + realesrgan")
def test_upscale_dir_enlarges_frames(real_clip, tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", real_clip, "-frames:v", "2",
         str(in_dir / "f%02d.png")],
        check=True, capture_output=True,
    )
    upscale.upscale_dir(str(in_dir), str(out_dir), scale=4, model="realesrgan-x4plus",
                        model_dir=MODEL_DIR)

    outs = sorted(os.listdir(out_dir))
    assert len(outs) == 2

    def dims(p):
        return subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0", p],
            check=True, capture_output=True, text=True,
        ).stdout.strip()

    # source frames are 288x512 -> 4x -> 1152x2048
    assert dims(str(out_dir / outs[0])) == "1152,2048"
