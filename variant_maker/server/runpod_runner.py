"""GPU runner: same Runner protocol as LocalRunner, but compute runs on a RunPod serverless
worker. Source/variants move through object storage; progress streams back as chunks."""
from __future__ import annotations

import os
from typing import Callable

from .events import VariantEvent
from .runner import SourceResult, VariantResult
from .runpod_client import RunPodClient
from .storage import ObjectStore

DEFAULT_PRESET = "medium"
DEFAULT_PLATFORM = "tiktok"
DEFAULT_QUALITY_MODE = "hq"   # Tier-2 neural upscale on the GPU
MAX_REGEN = 3


class RunPodServerlessRunner:
    def __init__(self, store: ObjectStore, client: RunPodClient) -> None:
        self._store = store
        self._client = client

    def run(self, source_path: str, *, count: int, out_dir: str, source_id: str,
            on_event: Callable[[VariantEvent], None]) -> SourceResult:
        basename = os.path.basename(source_path)
        source_key = f"inputs/{source_id}/{basename}"
        self._store.put(source_key, source_path)

        payload = {"input": {
            "source_key": source_key, "source_id": source_id, "count": count,
            "preset": DEFAULT_PRESET, "platform": DEFAULT_PLATFORM,
            "quality_mode": DEFAULT_QUALITY_MODE, "max_regen": MAX_REGEN,
        }}

        variants_meta: list[dict] = []
        manifest_key = None
        for chunk in self._client.stream_run(payload):
            if chunk.get("type") == "progress":
                e = chunk["event"]
                on_event(VariantEvent(
                    source_id=source_id, index=e["index"], state=e["state"],
                    attempt=e.get("attempt", 0), max_attempts=e.get("max_attempts", 0),
                    status=e.get("status"), quality=e.get("quality"),
                    filename=e.get("filename"),
                ))
            elif chunk.get("type") == "result":
                variants_meta = chunk.get("variants", [])
                manifest_key = chunk.get("manifest_key")

        os.makedirs(out_dir, exist_ok=True)
        variants = []
        for v in variants_meta:
            local = os.path.join(out_dir, v["filename"])
            self._store.get(v["key"], local)
            variants.append(VariantResult(index=v["index"], filename=v["filename"],
                                          status=v["status"], quality=v["quality"], path=local))
        manifest_path = os.path.join(out_dir, "manifest.json")
        if manifest_key:
            self._store.get(manifest_key, manifest_path)
        return SourceResult(variants=variants, manifest_path=manifest_path)
