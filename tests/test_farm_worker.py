"""GPU worker entry: run_job() = one sweep -> JSON-serializable summary. The RunPod
serverless handler is a thin wrapper over this. Config arrives inline (control plane), via a
path, or via $VARIANT_FARM_CONFIG. Tested with FakeDrive; no real Google, no GPU."""
import json

import pytest
import yaml

from variant_maker.farm import worker
from farm_fakes import FakeDrive
from conftest import HAS_FFMPEG


def _cfg_dict(in_id, out_id):
    return {
        "auth": {"service_account_json": "x.json"},
        "defaults": {"preset": "subtle", "count": 1, "platform": "none", "quality": "fast"},
        "poll_minutes": 15,
        "clients": {"acme": {"input_folder_id": in_id, "output_folder_id": out_id}},
    }


@pytest.mark.integration
@pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")
def test_run_job_inline_config_renders_and_returns_summary(sample_clip, tmp_path):
    fake = FakeDrive()
    in_id, out_id = fake.make_folder("in"), fake.make_folder("out")
    fake.put_file("clip.mp4", sample_clip, parent=in_id)

    out = worker.run_job({
        "config": _cfg_dict(in_id, out_id),
        "ledger_path": str(tmp_path / "l.json"), "work_dir": str(tmp_path / "w"),
    }, drive=fake)

    assert out["done"] == 1 and out["failed"] == 0
    json.dumps(out)  # must be JSON-serializable for the serverless response


def test_run_job_resolves_config_from_path(tmp_path):
    p = tmp_path / "farm.yaml"
    p.write_text(yaml.safe_dump(_cfg_dict("IN", "OUT")))  # folders absent in fake -> no work

    out = worker.run_job({
        "config_path": str(p),
        "ledger_path": str(tmp_path / "l.json"), "work_dir": str(tmp_path / "w"),
    }, drive=FakeDrive())

    assert out == {"new": 0, "done": 0, "failed": 0, "skipped": 0, "corrupt_dropped": 0}


def test_run_job_resolves_config_from_env(tmp_path, monkeypatch):
    p = tmp_path / "farm.yaml"
    p.write_text(yaml.safe_dump(_cfg_dict("IN", "OUT")))
    monkeypatch.setenv("VARIANT_FARM_CONFIG", str(p))

    out = worker.run_job({
        "ledger_path": str(tmp_path / "l.json"), "work_dir": str(tmp_path / "w"),
    }, drive=FakeDrive())

    assert out["done"] == 0
