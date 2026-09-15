"""BtbN dropped/recreates the rolling `latest` tag during each autobuild.

CI 34696701553 404'd `releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz`
at 13:32Z; the `latest` release came back at 13:34Z. Dated `autobuild-*` assets stay up.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "install_btbn_ffmpeg",
    ROOT / "deploy/runpod/install_btbn_ffmpeg.py",
)
mod = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(mod)


def _asset(name: str, url: str | None = None) -> dict:
    return {
        "name": name,
        "browser_download_url": url or f"https://example.test/{name}",
    }


def test_pick_linux64_gpl_skips_shared_and_other_arch():
    assets = [
        _asset("ffmpeg-N-1-linux64-gpl-shared.tar.xz"),
        _asset("ffmpeg-N-1-linuxarm64-gpl.tar.xz"),
        _asset("ffmpeg-N-1-linux64-gpl.tar.xz", "https://example.test/good"),
        _asset("ffmpeg-N-1-linux64-gpl.tar.xz.sha256"),
    ]
    picked = mod.pick_linux64_gpl_tarball(assets)
    assert picked["browser_download_url"] == "https://example.test/good"


def test_pick_linux64_gpl_accepts_master_latest_name():
    picked = mod.pick_linux64_gpl_tarball(
        [_asset("ffmpeg-master-latest-linux64-gpl.tar.xz", "https://example.test/rolling")]
    )
    assert picked["browser_download_url"] == "https://example.test/rolling"


def test_pick_linux64_gpl_raises_when_missing():
    with pytest.raises(ValueError, match="linux64-gpl"):
        mod.pick_linux64_gpl_tarball([_asset("ffmpeg-N-1-linux64-gpl-shared.tar.xz")])


def test_pick_stable_release_skips_rolling_latest_tag():
    """Rolling `latest` 404s while BtbN republishes it. Use dated autobuild."""
    releases = [
        {
            "tag_name": "latest",
            "assets": [
                _asset(
                    "ffmpeg-master-latest-linux64-gpl.tar.xz",
                    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz",
                )
            ],
        },
        {
            "tag_name": "autobuild-2026-09-12-13-12",
            "assets": [
                _asset(
                    "ffmpeg-N-126523-g884590dd4a-linux64-gpl.tar.xz",
                    "https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-09-12-13-12/ffmpeg-N-126523-g884590dd4a-linux64-gpl.tar.xz",
                )
            ],
        },
    ]
    rel = mod.pick_stable_btbn_release(releases)
    assert rel["tag_name"] == "autobuild-2026-09-12-13-12"
    url = mod.tarball_url(rel)
    assert "autobuild-2026-09-12-13-12" in url
    assert "download/latest/" not in url


def test_pick_stable_release_falls_back_to_latest_if_no_autobuild():
    releases = [
        {
            "tag_name": "latest",
            "assets": [_asset("ffmpeg-master-latest-linux64-gpl.tar.xz")],
        }
    ]
    rel = mod.pick_stable_btbn_release(releases)
    assert rel["tag_name"] == "latest"


def test_copy_bins_from_n_prefixed_tree(tmp_path: Path):
    tree = tmp_path / "src" / "ffmpeg-N-126523-g884590dd4a-linux64-gpl" / "bin"
    tree.mkdir(parents=True)
    (tree / "ffmpeg").write_bytes(b"ffmpeg-bin")
    (tree / "ffprobe").write_bytes(b"ffprobe-bin")
    dest = tmp_path / "bin"
    dest.mkdir()
    mod.copy_ffmpeg_bins(tmp_path / "src", dest)
    assert (dest / "ffmpeg").read_bytes() == b"ffmpeg-bin"
    assert (dest / "ffprobe").read_bytes() == b"ffprobe-bin"


def test_fast_dockerfile_installs_farm_extra_for_drive_export():
    text = (ROOT / "deploy/runpod/Dockerfile.fast").read_text()
    assert "[serverless,farm]" in text or "[farm,serverless]" in text


def test_dockerfiles_install_via_script_not_rolling_latest_url():
    paths = [
        ROOT / "deploy/runpod/Dockerfile.fast",
        ROOT / "deploy/runpod/Dockerfile",
        ROOT / "deploy/railway/Dockerfile",
    ]
    for path in paths:
        text = path.read_text()
        assert "releases/download/latest/" not in text, path
        assert "install_btbn_ffmpeg.py" in text, path
