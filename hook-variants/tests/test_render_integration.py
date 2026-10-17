from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from hook_variants.cli import main
from hook_variants.handoff import export_for_lab
from hook_variants.probe import probe
from hook_variants.styles import fonts_dir, get_style, package_root
from hook_variants.types import HookParams

pytestmark = pytest.mark.integration

FFMPEG = shutil.which("ffmpeg")


def _make_clip(path: Path) -> Path:
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=0x2a4a6b:s=720x1280:d=1.2:r=30",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return path


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg not installed")
def test_probe_even_dimensions(tmp_path: Path) -> None:
    clip = _make_clip(tmp_path / "src.mp4")
    info = probe(clip)
    assert info.width == 720
    assert info.height == 1280
    assert info.duration_s > 1.0
    assert info.has_audio is False


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg not installed")
def test_cli_renders_three_presets(tmp_path: Path) -> None:
    clip = _make_clip(tmp_path / "talk.mp4")
    out = tmp_path / "hooks"
    code = main(
        [
            str(clip),
            "--text",
            "this is why it hits",
            "-n",
            "3",
            "--lock-text",
            "--seed",
            "look",
            "--out",
            str(out),
        ]
    )
    assert code == 0
    mp4s = sorted(out.glob("*.mp4"))
    stills = sorted(out.glob("*.jpg"))
    asses = sorted(out.glob("*.ass"))
    assert len(mp4s) == 3
    assert len(stills) == 3
    assert len(asses) == 3
    manifest = (out / "manifest.json").read_text(encoding="utf-8")
    assert "tiktok-classic-box" in manifest or "edits-classic-outline" in manifest
    dest = tmp_path / "inbox"
    copied = export_for_lab(out, dest)
    assert len(copied) == 3
    assert (dest / "HANDOFF.md").is_file()


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg not installed")
def test_fonts_dir_has_three_families() -> None:
    root = package_root()
    for style_id in (
        "tiktok-classic-box",
        "edits-classic-outline",
        "edits-strong",
    ):
        style = get_style(style_id, root)
        assert (fonts_dir() / style.font_file).is_file()
        HookParams(0, "x", style_id, "top")
