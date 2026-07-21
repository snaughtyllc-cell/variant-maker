"""`variant-server` — launch the local control-plane API."""
from __future__ import annotations

import argparse
import os
import sys

from fastapi import FastAPI

from .app import create_app
from .drive_config import ENV_SA_JSON
from .jobs import JobStore
from .runner import LocalRunner, Runner
from .runpod_client import HttpRunPodClient
from .runpod_runner import RunPodServerlessRunner
from .storage import S3ObjectStore
from .workspace import Workspace

_RUNPOD_ENV = ("RUNPOD_ENDPOINT_ID", "RUNPOD_API_KEY", "R2_ENDPOINT", "R2_BUCKET",
               "R2_ACCESS_KEY", "R2_SECRET_KEY")


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
        client = HttpRunPodClient(endpoint_id=os.environ["RUNPOD_ENDPOINT_ID"],
                                  api_key=os.environ["RUNPOD_API_KEY"])
        return RunPodServerlessRunner(store, client)
    raise SystemExit(f"unknown runner: {kind!r}")


def build_app(data_dir: str, runner_kind: str = "local") -> FastAPI:
    return create_app(JobStore(Workspace(data_dir), make_runner(runner_kind)),
                      sa_json_path=os.environ.get(ENV_SA_JSON))


def main() -> None:
    p = argparse.ArgumentParser(prog="variant-server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--data-dir", default="./.vmdata")
    p.add_argument("--runner", choices=("local", "runpod"), default="local")
    args = p.parse_args()

    import uvicorn
    uvicorn.run(build_app(args.data_dir, args.runner), host=args.host, port=args.port)
    sys.exit(0)
