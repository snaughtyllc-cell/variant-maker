import os
import shutil
import subprocess
import pytest

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
REAL_CLIP_PATH = os.path.join(FIXTURES_DIR, "real_src.mp4")


@pytest.fixture(scope="session")
def sample_clip(tmp_path_factory):
    """A short, colorful, bt709-tagged clip for integration tests."""
    if not HAS_FFMPEG:
        pytest.skip("ffmpeg/ffprobe not available")
    out = tmp_path_factory.mktemp("fixtures") / "src.mp4"
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=15:duration=1",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-colorspace", "bt709", "-color_primaries", "bt709",
        "-color_trc", "bt709", "-color_range", "tv",
        "-c:a", "aac", "-shortest", str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return str(out)


@pytest.fixture(scope="session")
def real_clip():
    """Real short-form camera footage (vertical, bt709/tv, real grain + skin tones).

    Committed under tests/fixtures/ — the synthetic testsrc2 pattern has extreme primary
    saturation and clean edges; this exercises the color path on actual footage, where a
    dropped tag / range bug shows up as the real-world wash-out symptom.
    """
    if not HAS_FFMPEG:
        pytest.skip("ffmpeg/ffprobe not available")
    if not os.path.exists(REAL_CLIP_PATH):
        pytest.skip(f"real fixture missing: {REAL_CLIP_PATH}")
    return REAL_CLIP_PATH


def mean_saturation(path: str) -> float:
    """Mean SATAVG across frames via ffprobe + signalstats lavfi graph."""
    cmd = [
        "ffprobe", "-v", "error", "-f", "lavfi",
        "-i", f"movie={path},signalstats",
        "-show_entries", "frame_tags=lavfi.signalstats.SATAVG",
        "-of", "default=noprint_wrappers=1:nokey=1",
    ]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True)
    vals = [float(x) for x in out.stdout.split() if x.strip()]
    return sum(vals) / len(vals) if vals else 0.0
