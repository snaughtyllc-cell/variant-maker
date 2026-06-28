"""`variant-farm` — the headless worker entry point.

`variant-farm run --config farm.yaml` does ONE idempotent sweep and exits; an external
scheduler (cron) runs it every `poll_minutes`. No daemon, no queue — honors the local-CLI
scope. The Drive client is injectable (`sweep(..., drive=...)`) so the whole sweep is
testable with a fake; the real GoogleDrive is built from the config's service account.
"""
from __future__ import annotations

import click

from .config import load
from .ledger import Ledger
from .runner import SweepSummary, run_sweep


def sweep(config_path: str, *, ledger_path: str, work_dir: str, drive=None) -> SweepSummary:
    cfg = load(config_path)
    if drive is None:
        from .drive import GoogleDrive
        drive = GoogleDrive(cfg.auth.service_account_json)
    return run_sweep(cfg, drive, ledger=Ledger(ledger_path), work_dir=work_dir)


@click.group()
def main() -> None:
    """Drive farm worker."""


@main.command()
@click.option("--config", "config_path", required=True,
              type=click.Path(exists=True, dir_okay=False), help="farm config YAML")
@click.option("--ledger", "ledger_path", default="./farm-ledger.json", show_default=True,
              type=click.Path(), help="processed-set ledger (sha256-keyed)")
@click.option("--work-dir", default="./.farm-work", show_default=True, type=click.Path(),
              help="scratch dir for downloads/renders")
def run(config_path: str, ledger_path: str, work_dir: str) -> None:
    """One idempotent sweep across all clients, then exit."""
    summary = sweep(config_path, ledger_path=ledger_path, work_dir=work_dir)
    click.echo(str(summary))


if __name__ == "__main__":
    main()
