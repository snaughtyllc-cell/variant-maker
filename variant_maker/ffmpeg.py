"""STUB — Phase 5. Build + run one ffmpeg invocation per variant.

Must: apply color.output_color_args(...) on OUTPUT, -map_metadata -1, -fflags +bitexact,
libx264 with sampled crf/gop, aac audio. Return the exact command string for the manifest.
"""
from __future__ import annotations

import subprocess


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def render_variant(*args, **kwargs):
    raise NotImplementedError("Phase 5: build full cmd, render, return (path, cmd_str)")
