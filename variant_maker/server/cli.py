"""`variant-server` — launch the local control-plane API."""
from __future__ import annotations

import argparse
import os
import sys

from fastapi import FastAPI

from .app import create_app
from .drive_config import ENV_SA_JSON
from .jobs import JobStore
from .runner import LocalRunner, RoutingRunner, Runner, fast_local_max_from_env
from .runpod_client import HttpRunPodClient
from .runpod_runner import RunPodServerlessRunner
from .storage import S3ObjectStore
from .workspace import Workspace

_RUNPOD_ENV = ("RUNPOD_ENDPOINT_ID", "RUNPOD_API_KEY", "R2_ENDPOINT", "R2_BUCKET",
               "R2_ACCESS_KEY", "R2_SECRET_KEY")
FAST_ENDPOINT_ENV = "RUNPOD_FAST_ENDPOINT_ID"


def resolve_runner(kind: str | None) -> str:
    """Explicit --runner wins. Otherwise use RunPod when its env is complete."""
    if kind:
        return kind
    if all(os.environ.get(k) for k in _RUNPOD_ENV):
        return "runpod"
    return "local"


def _fast_endpoint_id() -> str | None:
    raw = (os.environ.get(FAST_ENDPOINT_ENV) or "").strip()
    return raw or None


def make_runner(kind: str) -> Runner:
    if kind == "local":
        return LocalRunner()
    if kind == "runpod":
        missing = [k for k in _RUNPOD_ENV if not os.environ.get(k)]
        if missing:
            raise SystemExit(f"--runner runpod requires env vars: {', '.join(missing)}")
        store = S3ObjectStore(
            endpoint_url=os.environ["R2_ENDPOINT"], bucket=os.environ["R2_BUCKET"],
            access_key=os.environ["R2_ACCESS_KEY"], secret_key=os.environ["R2_SECRET_KEY"])
        api_key = os.environ["RUNPOD_API_KEY"]
        gpu = RunPodServerlessRunner(
            store,
            HttpRunPodClient(endpoint_id=os.environ["RUNPOD_ENDPOINT_ID"], api_key=api_key),
        )
        fast_id = _fast_endpoint_id()
        fast = None
        if fast_id:
            fast = RunPodServerlessRunner(
                store,
                HttpRunPodClient(endpoint_id=fast_id, api_key=api_key),
            )
        return RoutingRunner(
            LocalRunner(),
            gpu,
            fast_remote=fast,
            max_local_fast=fast_local_max_from_env(),
        )
    raise SystemExit(f"unknown runner: {kind!r}")


def build_app(data_dir: str, runner_kind: str = "local") -> FastAPI:
    ws = Workspace(data_dir)
    return create_app(
        JobStore(ws, make_runner(runner_kind)),
        sa_json_path=os.environ.get(ENV_SA_JSON),
        oauth_token_path=ws.oauth_token_path(),
        enable_workflow_poller=True,
    )


def main() -> None:
    p = argparse.ArgumentParser(prog="variant-server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--data-dir", default="./.vmdata")
    p.add_argument("--runner", choices=("local", "runpod"), default=None,
                    help="default: runpod when RUNPOD_* + R2_* env is set, else local")
    args = p.parse_args()

    import uvicorn
    uvicorn.run(build_app(args.data_dir, resolve_runner(args.runner)),
                host=args.host, port=args.port)
    sys.exit(0)
