import os, subprocess, tempfile
from variant_maker import uniqueness

def _tiny_mp4(path, *, color="black"):
    # 1s 64x64 solid via lavfi
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=64x64:d=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", path,
    ], check=True, capture_output=True)

def test_identical_videos_score_near_zero():
    with tempfile.TemporaryDirectory() as d:
        a = os.path.join(d, "a.mp4"); b = os.path.join(d, "b.mp4")
        _tiny_mp4(a); _tiny_mp4(b)
        r = uniqueness.score_uniqueness(a, b, n_frames=4)
        assert r["uniqueness_metric"] == "phash_hist_v1"
        assert r["uniqueness"] is not None and r["uniqueness"] < 0.05

def test_different_colors_score_higher():
    with tempfile.TemporaryDirectory() as d:
        a = os.path.join(d, "a.mp4"); b = os.path.join(d, "b.mp4")
        _tiny_mp4(a, color="black"); _tiny_mp4(b, color="white")
        r = uniqueness.score_uniqueness(a, b, n_frames=4, target=0.35)
        assert r["uniqueness"] > 0.2
        assert r["uniqueness_status"] in ("ok", "below_target")

def test_missing_file_unknown():
    r = uniqueness.score_uniqueness("/nope/a.mp4", "/nope/b.mp4")
    assert r["uniqueness"] is None and r["uniqueness_status"] == "unknown"

def test_invalid_probe_duration_unknown(monkeypatch):
    def fake_probe(_path):
        raise ValueError("no valid duration in ffprobe output: 'N/A'")

    monkeypatch.setattr(uniqueness, "_probe_duration", fake_probe)
    with tempfile.TemporaryDirectory() as d:
        a = os.path.join(d, "a.mp4")
        _tiny_mp4(a)
        r = uniqueness.score_uniqueness(a, a, n_frames=2)
        assert r["uniqueness"] is None and r["uniqueness_status"] == "unknown"
