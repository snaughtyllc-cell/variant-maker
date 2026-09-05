"""GPU runner: same Runner protocol as LocalRunner, but compute runs on a RunPod serverless
worker. Source/variants move through object storage; progress streams back as chunks."""
from __future__ import annotations

import os
from collections.abc import Callable

from .events import VariantEvent
from .media_links import is_jpeg_name, output_key
from .runner import (
    DEFAULT_PLATFORM,
    DEFAULT_PRESET,
    MAX_REGEN,
    MIN_BITS_VS_PEERS,
    UNIQ_STRENGTHS,
    UNIQUENESS_TARGET,
    SourceResult,
    VariantResult,
    encode_jobs_for_worker,
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
    def __init__(self, store: ObjectStore, client: RunPodClient,
                 *, keep_local_media: bool = False) -> None:
        self._store = store
        self._client = client
        self._keep_local_media = keep_local_media

    @property
    def endpoint_id(self) -> str | None:
        return getattr(self._client, "endpoint_id", None)

    def run(self, source_path: str, *, count: int, out_dir: str, source_id: str,
            on_event: Callable[[VariantEvent], None],
            allow_creative_escalate: bool = True,
            quality_mode: str | None = None,
            cancel_token=None,
            drive_file_id: str | None = None,
            drive_access_token: str | None = None,
            source_object_key: str | None = None,
            output_prefix: str | None = None,
            tenant_id: str | None = None,
            job_id: str | None = None,
            attempt_id: str | None = None,
            **_kwargs) -> SourceResult:
        basename = os.path.basename(source_path) if source_path else "source.mp4"
        if drive_file_id:
            basename = os.path.basename(basename) or "source.mp4"
        source_key = source_object_key or f"inputs/{source_id}/{basename}"
        if source_path and os.path.isfile(source_path):
            self._store.put(source_key, source_path)
        elif drive_file_id:
            pass  # worker downloads with a job-scoped access token
        elif not getattr(self._store, "exists", lambda _k: False)(source_key):
            raise FileNotFoundError(f"source missing locally and in object storage: {source_key}")

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
            "jobs": encode_jobs_for_worker(quality_mode, count),
            "rubberband": False,
            "audio_uniqueness": False,
        }}
        if output_prefix:
            payload["input"]["output_prefix"] = output_prefix
        if tenant_id:
            payload["input"]["tenant_id"] = tenant_id
            payload["input"]["job_id"] = job_id
            payload["input"]["attempt_id"] = attempt_id
        if drive_file_id:
            payload["input"]["drive_file_id"] = drive_file_id
            payload["input"]["drive_access_token"] = drive_access_token
            payload["input"]["filename"] = basename
        return self._consume_stream(
            self._client.stream_run(payload, cancel_token=cancel_token),
            out_dir=out_dir, source_id=source_id, on_event=on_event,
            output_prefix=output_prefix,
        )

    def resume_run(self, source_path: str, *, count: int, out_dir: str, source_id: str,
                   on_event: Callable[[VariantEvent], None],
                   allow_creative_escalate: bool = True,
                   quality_mode: str | None = None,
                   cancel_token=None, runpod_job_id: str,
                   output_prefix: str | None = None, **_kwargs) -> SourceResult:
        """Reconnect to an in-flight RunPod job after Studio restart (no new /run)."""
        del source_path, count, allow_creative_escalate, quality_mode
        resume = getattr(self._client, "stream_resume", None)
        if not callable(resume):
            raise TypeError("RunPod client cannot resume a cloud job")
        return self._consume_stream(
            resume(runpod_job_id, cancel_token=cancel_token),
            out_dir=out_dir, source_id=source_id, on_event=on_event,
            output_prefix=output_prefix,
        )

    def _fetch_named(self, source_id: str, out_dir: str, name: str | None,
                     output_prefix: str | None = None) -> None:
        if not name:
            return
        base = os.path.basename(str(name))
        if base in ("", ".", "..") or base != str(name):
            return
        dest = os.path.join(out_dir, base)
        if os.path.isfile(dest) and os.path.getsize(dest) > 0:
            return
        keys = []
        if output_prefix:
            keys.append(f"{output_prefix.rstrip('/')}/{base}")
        keys.append(f"outputs/{source_id}/{base}")
        for key in keys:
            try:
                self._store.get(key, dest)
                return
            except Exception:
                continue

    def _consume_stream(self, chunks, *, out_dir: str, source_id: str,
                        on_event: Callable[[VariantEvent], None],
                        output_prefix: str | None = None) -> SourceResult:
        os.makedirs(out_dir, exist_ok=True)
        variants_meta: list[dict] = []
        manifest_key = None
        for chunk in chunks:
            if chunk.get("type") == "progress":
                e = chunk["event"]
                if e.get("state") == "looking":
                    self._fetch_named(
                        source_id, out_dir, e.get("look_src"),
                        output_prefix=output_prefix,
                    )
                    self._fetch_named(
                        source_id, out_dir, e.get("look_var"),
                        output_prefix=output_prefix,
                    )
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
                    look_status=e.get("look_status"),
                    look_mae=e.get("look_mae"),
                    look_mae_max=e.get("look_mae_max"),
                    look_src=e.get("look_src"),
                    look_var=e.get("look_var"),
                    look_frames=e.get("look_frames"),
                    look_artifact_sha256=e.get("look_artifact_sha256"),
                    look_review_t=e.get("look_review_t"),
                ))
            elif chunk.get("type") == "submitted":
                # JobStore persists runpod_job_id from cancel_token; nothing else.
                continue
            elif chunk.get("type") == "result":
                variants_meta = chunk.get("variants", [])
                manifest_key = chunk.get("manifest_key")

        variants = []
        for v in variants_meta:
            local = os.path.join(out_dir, v["filename"])
            key = v.get("key") or output_key(source_id, v["filename"])
            pull = self._keep_local_media or is_jpeg_name(v.get("filename"))
            if pull:
                self._store.get(key, local)
            self._fetch_named(
                source_id, out_dir, v.get("look_src"), output_prefix=output_prefix,
            )
            self._fetch_named(
                source_id, out_dir, v.get("look_var"), output_prefix=output_prefix,
            )
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
                look_status=v.get("look_status"),
                look_mae=v.get("look_mae"),
                look_mae_max=v.get("look_mae_max"),
                look_src=v.get("look_src"),
                look_var=v.get("look_var"),
                look_frames=list(v.get("look_frames") or []),
                look_artifact_sha256=v.get("look_artifact_sha256"),
                look_review_t=v.get("look_review_t"),
                object_key=key,
            ))
        manifest_path = os.path.join(out_dir, "manifest.json")
        if manifest_key:
            self._store.get(manifest_key, manifest_path)
        return SourceResult(variants=variants, manifest_path=manifest_path)

    def deliver_drive(self, *, folder_id: str, access_token: str,
                      files: list[dict], cancel_token=None) -> dict:
        payload = {"input": {
            "action": "deliver_drive",
            "folder_id": folder_id,
            "drive_access_token": access_token,
            "files": files,
        }}
        delivered = []
        for chunk in self._client.stream_run(payload, cancel_token=cancel_token):
            if chunk.get("type") == "result":
                delivered = chunk.get("delivered") or []
        return {"delivered": delivered, "folder_id": folder_id}

    def fetch_outputs(self, source_id: str, out_dir: str, filenames: list[str],
                      output_prefix: str | None = None) -> int:
        """Pull named files from object storage. Studio uses this for JPEG posters."""
        os.makedirs(out_dir, exist_ok=True)
        got = 0
        for raw in filenames:
            name = os.path.basename(raw)
            if not name or name in (".", ".."):
                continue
            if not self._keep_local_media and not is_jpeg_name(name):
                continue
            dest = os.path.join(out_dir, name)
            if os.path.isfile(dest) and os.path.getsize(dest) > 0:
                got += 1
                continue
            keys = []
            if output_prefix:
                keys.append(f"{output_prefix.rstrip('/')}/{name}")
            keys.append(f"outputs/{source_id}/{name}")
            for key in keys:
                try:
                    self._store.get(key, dest)
                    break
                except Exception:
                    continue
            if os.path.isfile(dest) and os.path.getsize(dest) > 0:
                got += 1
        return got
