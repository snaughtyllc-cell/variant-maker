"""Upload proxy: HDR/10-bit → SDR and 4K → long-edge ≤ 1920 (one encode)."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import HAS_FFMPEG

from variant_maker.normalize import (
    is_hdr_or_10bit,
    needs_size_proxy,
    needs_upload_proxy,
    proxy_output_size,
    proxy_scale_filter,
)
from variant_maker.probe import ColorTags, SourceInfo, probe


def test_needs_size_proxy_skips_1080_reels() -> None:
    assert needs_size_proxy(1080, 1920) is False
    assert needs_size_proxy(1920, 1080) is False
    assert needs_size_proxy(720, 1280) is False


def test_needs_size_proxy_catches_iphone_4k() -> None:
    assert needs_size_proxy(2160, 3840) is True
    assert needs_size_proxy(3840, 2160) is True
    assert needs_size_proxy(1921, 1080) is True


def test_proxy_output_size_portrait_4k() -> None:
    assert proxy_output_size(2160, 3840) == (1080, 1920)


def test_proxy_output_size_landscape_4k() -> None:
    assert proxy_output_size(3840, 2160) == (1920, 1080)


def test_proxy_output_size_already_1080() -> None:
    assert proxy_output_size(1080, 1920) == (1080, 1920)


def test_proxy_scale_filter_even_and_explicit() -> None:
    vf = proxy_scale_filter(2160, 3840)
    assert "scale=1080:1920" in vf
    assert "flags=lanczos" in vf


def test_is_hdr_or_10bit() -> None:
    assert is_hdr_or_10bit("yuv420p", "bt709") is False
    assert is_hdr_or_10bit("yuv420p10le", "bt709") is True
    assert is_hdr_or_10bit("yuv420p", "arib-std-b67") is True
    assert is_hdr_or_10bit("yuv420p", "smpte2084") is True


def _sdr_1080() -> SourceInfo:
    return SourceInfo(
        path="x.mp4",
        sha256="a" * 64,
        duration_s=3.0,
        width=1080,
        height=1920,
        fps=30.0,
        has_audio=True,
        color=ColorTags(range="tv", primaries="bt709", transfer="bt709", matrix="bt709"),
    )


def _sdr_4k() -> SourceInfo:
    return SourceInfo(
        path="x.mp4",
        sha256="a" * 64,
        duration_s=3.0,
        width=2160,
        height=3840,
        fps=30.0,
        has_audio=True,
        color=ColorTags(range="tv", primaries="bt709", transfer="bt709", matrix="bt709"),
    )


def test_needs_upload_proxy_1080_sdr_false() -> None:
    assert needs_upload_proxy(_sdr_1080(), pix_fmt="yuv420p") is False


def test_needs_upload_proxy_4k_sdr_true() -> None:
    assert needs_upload_proxy(_sdr_4k(), pix_fmt="yuv420p") is True


def test_needs_upload_proxy_hdr_1080_true() -> None:
    m = SourceInfo(
        path="x.mp4",
        sha256="a" * 64,
        duration_s=3.0,
        width=1080,
        height=1920,
        fps=30.0,
        has_audio=True,
        color=ColorTags(range="tv", primaries="bt2020", transfer="arib-std-b67", matrix="bt2020nc"),
    )
    assert needs_upload_proxy(m, pix_fmt="yuv420p") is True


@pytest.mark.integration
@pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")
def test_proxy_upload_downscales_oversized(tmp_path: Path) -> None:
    from variant_maker.ffmpeg import run
    from variant_maker.normalize import proxy_upload

    src = tmp_path / "big.mp4"
    dest = tmp_path / "proxy.mp4"
    # 2000×1120 is just over 1920 long-edge; cheap to encode in CI.
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=0.4:size=2000x1120:rate=24",
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            str(src),
        ]
    )
    meta = probe(str(src))
    assert needs_size_proxy(meta.width, meta.height)
    out = proxy_upload(src, dest, meta)
    assert out == dest
    got = probe(str(dest))
    w, h = proxy_output_size(meta.width, meta.height)
    assert got.width == w
    assert got.height == h
    assert dest.stat().st_size < src.stat().st_size
