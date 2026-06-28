"""`variant-farm run` — one sweep, print summary, exit. The Drive is injectable so the
sweep is testable end-to-end with the FakeDrive; the click layer is a thin wrapper."""
import os

import pytest
import yaml
from click.testing import CliRunner

from variant_maker.farm import cli
from variant_maker.farm.runner import SweepSummary
from farm_fakes import FakeDrive
from conftest import HAS_FFMPEG


def _write_cfg(path, in_id, out_id):
    path.write_text(yaml.safe_dump({
        "auth": {"service_account_json": "x.json"},
        "defaults": {"preset": "subtle", "count": 1, "platform": "none", "quality": "fast"},
        "poll_minutes": 15,
        "clients": {"acme": {"input_folder_id": in_id, "output_folder_id": out_id}},
    }))
    return str(path)


@pytest.mark.integration
@pytest.mark.skipif(not HAS_FFMPEG, reason="needs ffmpeg")
def test_sweep_helper_runs_with_injected_drive(sample_clip, tmp_path):
    fake = FakeDrive()
    in_id, out_id = fake.make_folder("in"), fake.make_folder("out")
    fake.put_file("clip.mp4", sample_clip, parent=in_id)
    cfg = _write_cfg(tmp_path / "farm.yaml", in_id, out_id)
    ledger_path = str(tmp_path / "ledger.json")

    summary = cli.sweep(cfg, ledger_path=ledger_path, work_dir=str(tmp_path / "w"), drive=fake)

    assert summary.done == 1
    assert os.path.exists(ledger_path)


def test_cli_run_invokes_sweep_and_prints_summary(monkeypatch, tmp_path):
    seen = {}

    def fake_sweep(config_path, *, ledger_path, work_dir, drive=None):
        seen.update(config_path=config_path, ledger_path=ledger_path, work_dir=work_dir)
        return SweepSummary(new=2, done=2)

    monkeypatch.setattr(cli, "sweep", fake_sweep)
    cfg = tmp_path / "farm.yaml"
    cfg.write_text("clients: {}\n")  # only needs to exist; sweep is stubbed

    res = CliRunner().invoke(cli.main, [
        "run", "--config", str(cfg),
        "--ledger", str(tmp_path / "l.json"), "--work-dir", str(tmp_path / "w"),
    ])

    assert res.exit_code == 0, res.output
    assert seen["config_path"] == str(cfg)
    assert seen["ledger_path"] == str(tmp_path / "l.json")
    assert "done=2" in res.output


def test_cli_run_requires_config():
    res = CliRunner().invoke(cli.main, ["run"])
    assert res.exit_code != 0


def test_cli_auth_command_is_wired():
    # --help must work without the google OAuth libs (import is lazy inside the command)
    res = CliRunner().invoke(cli.main, ["auth", "--help"])
    assert res.exit_code == 0
    assert "client-secrets" in res.output and "token" in res.output
