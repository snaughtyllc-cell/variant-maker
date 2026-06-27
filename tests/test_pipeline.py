import json
import os

import pytest

from variant_maker import pipeline
from variant_maker.probe import probe
from conftest import HAS_FFMPEG


def _config(real_clip, out, **ov):
    cfg = {
        "input": real_clip, "count": 2, "preset": "medium", "platform": "reels",
        "quality_mode": "fast", "seed": 12345, "out": out, "quality_floor": 90.0,
        "max_regen": 3, "rotate": "never", "flip": "never", "jobs": 1,
        "dry_run": False, "verbose": False,
    }
    cfg.update(ov)
    return cfg


@pytest.mark.integration
@pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")
def test_pipeline_produces_variants_and_manifest(real_clip, tmp_path):
    out = str(tmp_path / "out")
    m = pipeline.run(_config(real_clip, out, count=2))

    mpath = os.path.join(out, "manifest.json")
    assert os.path.exists(mpath)
    data = json.load(open(mpath))

    assert len(data["variants"]) == 2
    for v in data["variants"]:
        assert v["platform_result"] is None          # the detector bridge stays honest
        assert v["ffmpeg_cmd"].startswith("ffmpeg")
        assert v["output_sha256"]
        assert v["quality"]["passed"] is True
        assert os.path.exists(os.path.join(out, v["filename"]))

    assert data["run"]["master_seed"] == 12345
    assert data["run"]["preset"] == "medium" and data["run"]["platform"] == "reels"
    assert data["run"]["ffmpeg_version"]                # Codex #8: pin the encoder version
    assert data["source"]["sha256"] == probe(real_clip).sha256
    assert m.variants[0].filename == data["variants"][0]["filename"]


@pytest.mark.integration
@pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")
def test_pipeline_filenames_are_reproducible(real_clip, tmp_path):
    m1 = pipeline.run(_config(real_clip, str(tmp_path / "a"), count=1))
    m2 = pipeline.run(_config(real_clip, str(tmp_path / "b"), count=1))
    assert [v.filename for v in m1.variants] == [v.filename for v in m2.variants]


@pytest.mark.integration
@pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")
def test_pipeline_dry_run_renders_nothing(real_clip, tmp_path):
    out = str(tmp_path / "dry")
    m = pipeline.run(_config(real_clip, out, dry_run=True, count=2))

    assert not os.path.exists(os.path.join(out, "manifest.json"))
    if os.path.isdir(out):
        assert [f for f in os.listdir(out) if f.endswith(".mp4")] == []
    assert len(m.variants) == 2
    assert all(v.ffmpeg_cmd.startswith("ffmpeg") for v in m.variants)


@pytest.mark.integration
@pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")
def test_cli_dry_run_smoke(real_clip):
    from click.testing import CliRunner
    from variant_maker.cli import main

    res = CliRunner().invoke(
        main, [real_clip, "--dry-run", "-n", "1", "--platform", "reels", "--seed", "1"]
    )
    assert res.exit_code == 0, res.output
    assert "ffmpeg" in res.output
