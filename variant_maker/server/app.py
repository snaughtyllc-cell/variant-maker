"""FastAPI control-plane app. Imported only with the `server` extra installed."""
from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="variant-maker control plane")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    return app
