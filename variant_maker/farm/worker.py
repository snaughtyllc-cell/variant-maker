"""GPU worker entry point — one sweep, returns a JSON-serializable summary.

This is what runs inside the Linux/NVIDIA serverless container: the RunPod handler
(deploy/runpod/handler.py) is a thin wrapper over `run_job`. It reuses `run_sweep` unchanged
— with $VARIANT_MAKER_UPSCALE_BACKEND=cuda, the engine's hq path resolves the CUDA backend,
so the spatial-corruption guard still gates every upload.

Config can arrive three ways (control plane > path > env), so the same image serves an
inline-job control plane or a cron-triggered standalone worker.
"""
from __future__ import annotations

import os

from .config import FarmConfig, from_dict, load
from .ledger import Ledger
from .runner import run_sweep

# Default to a PERSISTENT location: serverless instances are ephemeral, so the ledger must
# live on a mounted volume or idempotency resets every invocation (everything reprocessed).
_DEFAULT_LEDGER = "/runpod-volume/farm-ledger.json"
_DEFAULT_WORK = "/tmp/vm-farm"


def _resolve_config(inp: dict) -> FarmConfig:
    if inp.get("config") is not None:
        return from_dict(inp["config"])          # inline dict from the control plane
    path = inp.get("config_path") or os.environ.get("VARIANT_FARM_CONFIG")
    if not path:
        raise ValueError("no config: pass input.config, input.config_path, or $VARIANT_FARM_CONFIG")
    return load(path)


def run_job(inp: dict, *, drive=None) -> dict:
    """Run one farm sweep. `inp` is the serverless job input; `drive` is injectable for tests
    (defaults to the real GoogleDrive built from the config's service account)."""
    cfg = _resolve_config(inp)
    ledger_path = inp.get("ledger_path") or os.environ.get("VARIANT_FARM_LEDGER", _DEFAULT_LEDGER)
    work_dir = inp.get("work_dir") or os.environ.get("VARIANT_FARM_WORK", _DEFAULT_WORK)
    if drive is None:
        from .drive import GoogleDrive
        drive = GoogleDrive(cfg.auth.service_account_json)

    s = run_sweep(cfg, drive, ledger=Ledger(ledger_path), work_dir=work_dir)
    return {"new": s.new, "done": s.done, "failed": s.failed,
            "skipped": s.skipped, "corrupt_dropped": s.corrupt_dropped}
