"""A deterministic Runner that needs no ffmpeg — for JobStore / app tests."""
from __future__ import annotations

import os
from typing import Callable

from variant_maker.server.events import VariantEvent
from variant_maker.server.runner import SourceResult, VariantResult


class FakeRunner:
    """plan: {variant_index: status}. Emits the full lifecycle and writes placeholder files."""

    def __init__(self, plan: dict[int, str] | None = None) -> None:
        # default (empty plan): every variant is "ok".
        # Pass a {variant_index: status} dict to override specific indices.
        self.plan = plan or {}

    def _status(self, i: int) -> str:
        return self.plan.get(i, "ok")

    def run(self, source_path: str, *, count: int, out_dir: str, source_id: str,
            on_event: Callable[[VariantEvent], None]) -> SourceResult:
        os.makedirs(out_dir, exist_ok=True)
        variants = []
        for i in range(1, count + 1):
            status = self._status(i)
            fname = f"v{i:02d}.mp4"
            on_event(VariantEvent(source_id=source_id, index=i, state="rendering"))
            on_event(VariantEvent(source_id=source_id, index=i, state="checking"))
            on_event(VariantEvent(
                source_id=source_id, index=i, state="done",
                status=status, quality={"vmaf": 95.0 if status == "ok" else 50.0},
                filename=fname,
            ))
            path = os.path.join(out_dir, fname)
            open(path, "w").close()
            variants.append(VariantResult(index=i, filename=fname, status=status,
                                          quality={"vmaf": 95.0}, path=path))
        mpath = os.path.join(out_dir, "manifest.json")
        open(mpath, "w").close()
        return SourceResult(variants=variants, manifest_path=mpath)
