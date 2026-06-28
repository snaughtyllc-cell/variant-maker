"""`variant-server` — launch the local control-plane API."""
from __future__ import annotations

import argparse

from fastapi import FastAPI

from .app import create_app
from .jobs import JobStore
from .runner import LocalRunner
from .workspace import Workspace


def build_app(data_dir: str) -> FastAPI:
    return create_app(JobStore(Workspace(data_dir), LocalRunner()))


def main() -> None:
    p = argparse.ArgumentParser(prog="variant-server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--data-dir", default="./.vmdata")
    args = p.parse_args()

    import uvicorn
    uvicorn.run(build_app(args.data_dir), host=args.host, port=args.port)
