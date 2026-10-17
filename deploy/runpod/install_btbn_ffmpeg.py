"""Install BtbN static ffmpeg+libvmaf into /usr/local/bin.

BtbN's rolling GitHub release tag `latest` is deleted and recreated around each
autobuild (CI 34696701553: wget exit 8 / HTTP 404 at 13:32Z; `latest` returned
at 13:34Z). Dated `autobuild-*` tarballs stay downloadable. Prefer those.

Override with FFMPEG_TARBALL_URL if GitHub API is unreachable.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

API_RELEASES = "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases?per_page=10"
USER_AGENT = "variant-maker-docker"
FALLBACK_TARBALL_URL = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/"
    "autobuild-2026-09-12-13-12/ffmpeg-N-126523-g884590dd4a-linux64-gpl.tar.xz"
)
BIN_DIR = Path("/usr/local/bin")


def pick_linux64_gpl_tarball(assets: list[dict]) -> dict:
    """Static linux64 GPL tarball only — not shared, not arm, not checksums."""
    for asset in assets:
        name = str(asset.get("name") or "")
        if not name.endswith("linux64-gpl.tar.xz"):
            continue
        if "shared" in name:
            continue
        return asset
    raise ValueError("no linux64-gpl tarball in BtbN release assets")


def pick_stable_btbn_release(releases: list[dict]) -> dict:
    """Skip rolling `latest` while a dated autobuild exists."""
    autobuilds = [
        rel for rel in releases if str(rel.get("tag_name") or "").startswith("autobuild-")
    ]
    pool = autobuilds or list(releases)
    last = None
    for rel in pool:
        try:
            pick_linux64_gpl_tarball(rel.get("assets") or [])
            return rel
        except ValueError as exc:
            last = exc
    raise ValueError(f"no BtbN linux64-gpl tarball in releases: {last}")


def tarball_url(release: dict) -> str:
    return str(pick_linux64_gpl_tarball(release.get("assets") or [])["browser_download_url"])


def copy_ffmpeg_bins(extract_root: Path, dest_bin: Path) -> None:
    ffmpeg = next(extract_root.glob("ffmpeg*/bin/ffmpeg"), None)
    if ffmpeg is None or not ffmpeg.is_file():
        raise FileNotFoundError(f"ffmpeg binary missing under {extract_root}")
    ffprobe = ffmpeg.parent / "ffprobe"
    if not ffprobe.is_file():
        raise FileNotFoundError(f"ffprobe missing next to {ffmpeg}")
    dest_bin.mkdir(parents=True, exist_ok=True)
    for src, name in ((ffmpeg, "ffmpeg"), (ffprobe, "ffprobe")):
        target = dest_bin / name
        shutil.copy2(src, target)
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _request(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=timeout)


def _get_json(url: str) -> object:
    last: Exception | None = None
    for attempt in range(6):
        try:
            with _request(url, timeout=30) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            time.sleep(min(2**attempt, 16))
    raise RuntimeError(f"GET {url} failed: {last}") from last


def resolve_tarball_url() -> str:
    override = os.environ.get("FFMPEG_TARBALL_URL", "").strip()
    if override:
        return override
    try:
        releases = _get_json(API_RELEASES)
        if not isinstance(releases, list):
            raise TypeError(f"unexpected releases payload: {type(releases)}")
        return tarball_url(pick_stable_btbn_release(releases))
    except (RuntimeError, TypeError, ValueError, urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"BtbN API failed ({exc}); using dated fallback", file=sys.stderr, flush=True)
        return FALLBACK_TARBALL_URL


def download(url: str, dest: Path) -> None:
    last: Exception | None = None
    for attempt in range(6):
        try:
            with _request(url, timeout=180) as resp, dest.open("wb") as out:
                shutil.copyfileobj(resp, out)
            if dest.stat().st_size < 1_000_000:
                raise RuntimeError(f"tarball too small: {dest.stat().st_size} bytes")
            return
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
            last = exc
            if dest.exists():
                dest.unlink()
            time.sleep(min(2**attempt, 16))
    raise RuntimeError(f"download {url} failed: {last}") from last


def extract_tarball(tarball: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tarball) as tar:
        tar.extractall(dest)


def verify_libvmaf(ffmpeg: Path) -> None:
    out = subprocess.check_output(
        [str(ffmpeg), "-hide_banner", "-filters"],
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if "libvmaf" not in out:
        raise SystemExit("installed ffmpeg has no libvmaf filter")


def main() -> None:
    url = resolve_tarball_url()
    print(f"BtbN ffmpeg {url}", flush=True)
    tarball = Path("/tmp/ffmpeg.tar.xz")
    work = Path("/tmp/ffmpeg-extract")
    if work.exists():
        shutil.rmtree(work)
    download(url, tarball)
    extract_tarball(tarball, work)
    copy_ffmpeg_bins(work, BIN_DIR)
    verify_libvmaf(BIN_DIR / "ffmpeg")
    tarball.unlink(missing_ok=True)
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
