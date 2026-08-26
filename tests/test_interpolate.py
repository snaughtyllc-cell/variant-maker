import os

import pytest

from variant_maker.neural import interpolate, upscale
from variant_maker.platforms import get_platform
from variant_maker.probe import ColorTags, SourceInfo


def _src(fps=30.0):
    return SourceInfo("in.mp4", "deadbeef", 10.0, 1080, 1920, fps, True,
                      ColorTags("tv", "bt709", "bt709", "bt709"))


def test_available_is_false_for_bogus_dir():
    assert interpolate.available("/nonexistent/rife") is False


def test_available_is_false_when_models_missing(tmp_path):
    d = tmp_path / "binonly"
    d.mkdir()
    (d / "rife-ncnn-vulkan").write_text("")
    assert interpolate.available(str(d)) is False


def test_build_interpolate_cmd_flags(tmp_path):
    d = tmp_path / "rife"
    (d / "models" / "rife-v4.6").mkdir(parents=True)
    binpath = d / "rife-ncnn-vulkan"
    binpath.write_text("")
    cmd = interpolate.build_interpolate_cmd(
        "in/", "out/", n_frames=48, model_dir=str(d),
    )
    assert cmd[0] == str(binpath)
    assert cmd[cmd.index("-i") + 1] == "in/"
    assert cmd[cmd.index("-o") + 1] == "out/"
    assert cmd[cmd.index("-n") + 1] == "48"
    assert cmd[cmd.index("-m") + 1].endswith(os.path.join("models", "rife-v4.6"))


def test_needed_when_speed_moves():
    reels = get_platform("reels")
    src = _src(fps=30.0)
    assert interpolate.needed({"video": {"speed": 1.02}}, src, reels) is True
    assert interpolate.needed({"video": {"speed": 1.0}}, src, reels) is False


def test_needed_when_fps_changes():
    reels = get_platform("reels")
    src = _src(fps=24.0)
    assert interpolate.needed({"video": {"speed": 1.0}}, src, reels) is True


def test_target_frame_count_slows_and_speeds():
    # 30 frames @ 30fps = 1s; speed 0.5 → 2s @ 30fps → 60 frames
    assert interpolate.target_frame_count(30, 30.0, 30.0, 0.5) == 60
    assert interpolate.target_frame_count(30, 30.0, 30.0, 2.0) == 15
    # 24fps source → 30fps dest, speed 1
    assert interpolate.target_frame_count(24, 24.0, 30.0, 1.0) == 30


def test_upscale_clip_defers_tempo_when_rife_available(monkeypatch):
    """HQ pre-render must skip ffmpeg fps/setpts when RIFE will own tempo."""
    captured = {}

    def fake_render(src, params, platform, out_path):
        captured["params"] = params
        raise RuntimeError("stop-after-pre-render")

    monkeypatch.setattr("variant_maker.ffmpeg.render_variant", fake_render)
    monkeypatch.setattr(interpolate, "available", lambda *a, **k: True)
    monkeypatch.setattr(interpolate, "needed", lambda *a, **k: True)

    src = _src(fps=30.0)
    params = {"video": {"speed": 1.02, "crf": 21}, "audio": {"speed": 1.02}}
    with pytest.raises(RuntimeError, match="stop-after-pre-render"):
        upscale.upscale_clip(src, params, "out.mp4", platform=get_platform("reels"))

    assert captured["params"]["video"].get("defer_tempo") is True
    assert "defer_tempo" not in params["video"]


def test_upscale_clip_no_defer_when_rife_unavailable(monkeypatch):
    captured = {}

    def fake_render(src, params, platform, out_path):
        captured["params"] = params
        raise RuntimeError("stop-after-pre-render")

    monkeypatch.setattr("variant_maker.ffmpeg.render_variant", fake_render)
    monkeypatch.setattr(interpolate, "available", lambda *a, **k: False)
    monkeypatch.setattr(interpolate, "needed", lambda *a, **k: True)

    src = _src(fps=30.0)
    params = {"video": {"speed": 1.02, "crf": 21}, "audio": {"speed": 1.02}}
    with pytest.raises(RuntimeError, match="stop-after-pre-render"):
        upscale.upscale_clip(src, params, "out.mp4", platform=get_platform("reels"))

    assert captured["params"]["video"].get("defer_tempo") is not True
    assert captured["params"] is params


def test_upscale_clip_interpolates_before_upscale(monkeypatch):
    """RIFE retimes the PNG dir; Real-ESRGAN is never required for this unit test."""
    seen = {}

    def fake_render(src, params, platform, out_path):
        open(out_path, "wb").close()
        return out_path, "ffmpeg-pre"

    def fake_run(cmd, check=True, capture_output=True):
        last = cmd[-1] if cmd else ""
        if isinstance(last, str) and last.endswith("f%06d.png"):
            d = os.path.dirname(last)
            for i in range(1, 4):
                open(os.path.join(d, f"f{i:06d}.png"), "wb").close()

    def fake_interp(in_dir, out_dir, *, n_frames, **_kw):
        os.makedirs(out_dir, exist_ok=True)
        for i in range(n_frames):
            open(os.path.join(out_dir, f"f{i + 1:06d}.png"), "wb").close()
        seen["n_in"] = sum(1 for n in os.listdir(in_dir) if n.endswith(".png"))
        seen["n_out"] = n_frames
        seen["rife_dir"] = out_dir
        return out_dir

    class FakeBackend:
        def upscale_dir(self, in_dir, out_dir, *, scale, model, fmt="png"):
            seen["upscale_in"] = in_dir
            raise RuntimeError("stop-after-rife")

        def command_str(self, *a, **k):
            return "upscale"

    monkeypatch.setattr("variant_maker.ffmpeg.render_variant", fake_render)
    monkeypatch.setattr("variant_maker.neural.upscale.subprocess.run", fake_run)
    monkeypatch.setattr(interpolate, "available", lambda *a, **k: True)
    monkeypatch.setattr(interpolate, "needed", lambda *a, **k: True)
    monkeypatch.setattr(interpolate, "interpolate_dir", fake_interp)

    src = _src(fps=30.0)
    params = {"video": {"speed": 0.5, "crf": 21}, "audio": {"speed": 0.5}}
    with pytest.raises(RuntimeError, match="stop-after-rife"):
        upscale.upscale_clip(
            src, params, "out.mp4", platform=get_platform("reels"), backend=FakeBackend(),
        )

    assert seen["n_in"] == 3
    assert seen["n_out"] == interpolate.target_frame_count(3, 30.0, 30.0, 0.5)
    assert seen["upscale_in"] == seen["rife_dir"]
