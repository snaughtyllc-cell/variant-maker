"""GPU runner: same Runner protocol as LocalRunner, but compute runs on a RunPod serverless
worker. Source/variants move through object storage; progress streams back as chunks."""
from __future__ import annotations

import os
from collections.abc import Callable

from .events import VariantEvent
from .runner import (
    DEFAULT_PLATFORM,
    DEFAULT_PRESET,
    MAX_REGEN,
    MIN_BITS_VS_PEERS,
    UNIQ_STRENGTHS,
    UNIQUENESS_TARGET,
    SourceResult,
    VariantResult,
    hq_job_limits,
    normalize_quality_mode,
)
from .runpod_client import RunPodClient
from .storage import ObjectStore

DEFAULT_QUALITY_MODE = "hq"   # Tier-2 neural upscale on the GPU


def _quality_mode() -> str:
    """VARIANT_QUALITY_MODE=fast skips Real-ESRGAN (team speed); default hq."""
    mode = os.environ.get("VARIANT_QUALITY_MODE", DEFAULT_QUALITY_MODE).strip().lower()
    return mode if mode in ("fast", "hq") else DEFAULT_QUALITY_MODE


class RunPodServerlessRunner:
    def __init__(self, store: ObjectStore, client: RunPodClient) -> None:
        self._store = store
        self._client = client

    def run(self, source_path: str, *, count: int, out_dir: str, source_id: str,
            on_event: Callable[[VariantEvent], None],
            allow_creative_escalate: bool = True,
            quality_mode: str | None = None,
            cancel_token=None) -> SourceResult:
        basename = os.path.basename(source_path)
        source_key = f"inputs/{source_id}/{basename}"
        self._store.put(source_key, source_path)

        quality_mode = normalize_quality_mode(quality_mode, default=_quality_mode())
        limits = hq_job_limits(quality_mode)
        payload = {"input": {
            "source_key": source_key, "source_id": source_id, "count": count,
            "preset": DEFAULT_PRESET, "platform": DEFAULT_PLATFORM,
            "quality_mode": quality_mode,
            "max_regen": limits.get("max_regen", MAX_REGEN),
            "allow_creative_escalate": limits.get(
                "allow_creative_escalate", allow_creative_escalate,
            ),
            "uniqueness_target": UNIQUENESS_TARGET,
            "uniq_strengths": limits.get("uniq_strengths", list(UNIQ_STRENGTHS)),
            "min_bits_vs_peers": MIN_BITS_VS_PEERS,
            "auto_tune": limits.get("auto_tune", True),
        }}

        variants_meta: list[dict] = []
        manifest_key = None
        for chunk in self._client.stream_run(payload, cancel_token=cancel_token):
            if chunk.get("type") == "progress":
                e = chunk["event"]
                on_event(VariantEvent(
                    source_id=source_id, index=e["index"], state=e["state"],
                    attempt=e.get("attempt", 0), max_attempts=e.get("max_attempts", 0),
                    status=e.get("status"), quality=e.get("quality"),
                    filename=e.get("filename"),
                    uniqueness=e.get("uniqueness"),
                    uniqueness_status=e.get("uniqueness_status"),
                    uniqueness_metric=e.get("uniqueness_metric"),
                    uniqueness_target=e.get("uniqueness_target"),
                    escalated=bool(e.get("escalated", False)),
                    preset_used=e.get("preset_used"),
                    strength_final=e.get("strength_final"),
                    platform_result=e.get("platform_result"),
                ))
            elif chunk.get("type") == "result":
                variants_meta = chunk.get("variants", [])
                manifest_key = chunk.get("manifest_key")

        os.makedirs(out_dir, exist_ok=True)
        variants = []
        for v in variants_meta:
            local = os.path.join(out_dir, v["filename"])
            self._store.get(v["key"], local)
            variants.append(VariantResult(
                index=v["index"], filename=v["filename"],
                status=v["status"], quality=v["quality"], path=local,
                uniqueness=v.get("uniqueness"),
                uniqueness_status=v.get("uniqueness_status"),
                uniqueness_metric=v.get("uniqueness_metric"),
                uniqueness_target=v.get("uniqueness_target"),
                preset_used=v.get("preset_used"),
                strength_final=v.get("strength_final"),
                escalated=bool(v.get("escalated", False)),
                platform_result=v.get("platform_result"),
            ))
        manifest_path = os.path.join(out_dir, "manifest.json")
        if manifest_key:
            self._store.get(manifest_key, manifest_path)
        return SourceResult(variants=variants, manifest_path=manifest_path)
