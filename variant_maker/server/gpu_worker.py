"""Worker core: download source -> pipeline.run (HQ) streaming progress -> upload variants.

`process_job` is a generator that yields the locked progress/result chunks. pipeline.run is
blocking and calls on_event synchronously, so it runs on a background thread and pushes events
into a queue that the generator drains (same threading pattern as JobStore)."""
from __future__ import annotations

import os
import queue
import threading
from collections.abc import Iterator

from .. import pipeline
from ..copyid import normalize_mode
from .runner import (
    DEFAULT_PLATFORM,
    DEFAULT_PRESET,
    MAX_REGEN,
    MIN_BITS_VS_PEERS,
    UNIQ_STRENGTHS,
    UNIQUENESS_TARGET,
    encode_jobs_for_worker,
)
from .storage import ObjectStore


def _progress_chunk(state: str, kw: dict) -> dict:
    return {"type": "progress", "event": {
        "index": kw.get("index"), "state": state,
        "attempt": kw.get("attempt", 0), "max_attempts": kw.get("max_attempts", 0),
        "status": kw.get("status"), "quality": kw.get("quality"),
        "filename": kw.get("filename"),
        "uniqueness": kw.get("uniqueness"),
        "uniqueness_status": kw.get("uniqueness_status"),
        "uniqueness_metric": kw.get("uniqueness_metric"),
        "uniqueness_target": kw.get("uniqueness_target"),
        "escalated": bool(kw.get("escalated", False)),
        "preset_used": kw.get("preset_used"),
        "strength_final": kw.get("strength_final"),
        "platform_result": kw.get("platform_result"),
        "look_status": kw.get("look_status"),
        "look_mae": kw.get("look_mae"),
        "look_src": kw.get("look_src"),
        "look_var": kw.get("look_var"),
    }}


def _flag(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def resolve_rotate(job_input: dict) -> str:
    """Studio often omits rotate. Safe is the compete default; never still wins if sent."""
    raw = job_input.get("rotate") or os.environ.get("VARIANT_MAKER_ROTATE") or "safe"
    raw = str(raw).strip().lower()
    return raw if raw in ("never", "safe") else "safe"


def resolve_us_metadata(job_input: dict) -> bool:
    """Off unless the job or VARIANT_MAKER_US_METADATA turns it on."""
    if "us_metadata" in job_input:
        return _flag(job_input["us_metadata"])
    return _flag(os.environ.get("VARIANT_MAKER_US_METADATA", ""))


def resolve_copyid(job_input: dict) -> str:
    """off | record | gate. Job wins; else VARIANT_MAKER_COPYID; else off."""
    if "copyid" in job_input and job_input.get("copyid") is not None:
        return normalize_mode(job_input.get("copyid"))
    return normalize_mode(os.environ.get("VARIANT_MAKER_COPYID"))


def _put_named(store: ObjectStore, prefix: str, out_dir: str, name: str | None) -> None:
    if not name:
        return
    base = os.path.basename(str(name))
    if base in ("", ".", "..") or base != str(name):
        return
    path = os.path.join(out_dir, base)
    if os.path.isfile(path):
        store.put(f"{prefix}/{base}", path)


def process_job(job_input: dict, store: ObjectStore, *, work_dir: str) -> Iterator[dict]:
    if str(job_input.get("action") or "") == "deliver_drive":
        yield from deliver_drive(job_input, store, work_dir=work_dir)
        return
    source_key = job_input.get("source_key")
    source_id = job_input["source_id"]
    count = job_input["count"]
    basename = os.path.basename(source_key or job_input.get("filename") or "source.mp4")

    in_path = os.path.join(work_dir, "in", basename)
    if job_input.get("drive_file_id") and job_input.get("drive_access_token"):
        os.makedirs(os.path.dirname(in_path), exist_ok=True)
        _download_drive_file(
            job_input["drive_file_id"], in_path, job_input["drive_access_token"],
        )
        if source_key:
            store.put(source_key, in_path)
    else:
        store.get(source_key, in_path)
    out_dir = os.path.join(work_dir, "out")
    os.makedirs(out_dir, exist_ok=True)
    output_prefix = str(job_input.get("output_prefix") or f"outputs/{source_id}").rstrip("/")

    quality_mode = job_input.get("quality_mode", "hq")
    auto_tune = job_input.get("auto_tune")
    if auto_tune is None:
        auto_tune = quality_mode != "hq"
    config = {
        "input": in_path, "out": out_dir, "count": count,
        "preset": job_input.get("preset", DEFAULT_PRESET),
        "platform": job_input.get("platform", DEFAULT_PLATFORM),
        "quality_mode": quality_mode,
        "max_regen": job_input.get("max_regen", MAX_REGEN),
        "jobs": encode_jobs_for_worker(
            quality_mode, count, requested=job_input.get("jobs"),
        ),
        "uniqueness_target": job_input.get("uniqueness_target", UNIQUENESS_TARGET),
        "uniq_strengths": job_input.get("uniq_strengths", list(UNIQ_STRENGTHS)),
        "min_bits_vs_peers": job_input.get("min_bits_vs_peers", MIN_BITS_VS_PEERS),
        "allow_creative_escalate": job_input.get("allow_creative_escalate", True),
        "auto_tune": auto_tune,
        "rubberband": job_input.get("rubberband", False),
        "audio_uniqueness": bool(job_input.get("audio_uniqueness", False)),
        "rotate": resolve_rotate(job_input),
        "us_metadata": resolve_us_metadata(job_input),
        "copyid": resolve_copyid(job_input),
    }

    q: queue.Queue = queue.Queue()
    DONE = object()
    holder: dict = {}

    def emit(state: str, **kw) -> None:
        if state == "looking":
            _put_named(store, output_prefix, out_dir, kw.get("look_src"))
            _put_named(store, output_prefix, out_dir, kw.get("look_var"))
        q.put(_progress_chunk(state, kw))

    def work() -> None:
        try:
            holder["manifest"] = pipeline.run(config, on_event=emit)
        except Exception as e:  # surface worker failure to the generator
            holder["error"] = e
        finally:
            q.put(DONE)

    t = threading.Thread(target=work, daemon=True)
    t.start()
    while True:
        item = q.get()
        if item is DONE:
            break
        yield item
    t.join()
    if "error" in holder:
        raise holder["error"]

    manifest = holder["manifest"]
    variants = []
    for v in manifest.variants:
        key = f"{output_prefix}/{v.filename}"
        store.put(key, os.path.join(out_dir, v.filename))
        _put_named(store, output_prefix, out_dir, getattr(v, "look_src", None))
        _put_named(store, output_prefix, out_dir, getattr(v, "look_var", None))
        variants.append({
            "index": v.index, "filename": v.filename,
            "status": v.status, "quality": v.quality, "key": key,
            "uniqueness": getattr(v, "uniqueness", None),
            "uniqueness_status": getattr(v, "uniqueness_status", None),
            "uniqueness_metric": getattr(v, "uniqueness_metric", None),
            "uniqueness_target": getattr(v, "uniqueness_target", None),
            "preset_used": getattr(v, "preset_used", None),
            "strength_final": getattr(v, "strength_final", None),
            "escalated": bool(getattr(v, "escalated", False)),
            "platform_result": getattr(v, "platform_result", None),
            "look_status": getattr(v, "look_status", None),
            "look_mae": getattr(v, "look_mae", None),
            "look_src": getattr(v, "look_src", None),
            "look_var": getattr(v, "look_var", None),
        })
    manifest_key = f"{output_prefix}/manifest.json"
    store.put(manifest_key, os.path.join(out_dir, "manifest.json"))
    yield {"type": "result", "variants": variants, "manifest_key": manifest_key}


def _download_drive_file(file_id: str, dest: str, access_token: str) -> None:
    from variant_maker.farm.drive import GoogleDrive
    GoogleDrive(access_token=access_token).download(file_id, dest)


def deliver_drive(job_input: dict, store: ObjectStore, *, work_dir: str) -> Iterator[dict]:
    """Upload object-storage keys to Drive using a job-scoped access token."""
    token = job_input.get("drive_access_token")
    folder_id = job_input.get("folder_id")
    files = job_input.get("files") or []
    if not token or not folder_id:
        raise ValueError("deliver_drive requires drive_access_token and folder_id")
    from variant_maker.farm.drive import GoogleDrive
    drive = GoogleDrive(access_token=str(token))
    uploaded = []
    for item in files:
        key = item.get("key")
        name = item.get("name") or (os.path.basename(key) if key else "variant.mp4")
        if not key:
            continue
        local = os.path.join(work_dir, "deliver", os.path.basename(str(key)))
        store.get(str(key), local)
        drive_id = drive.upload(local, str(folder_id), name=name)
        uploaded.append({"key": key, "name": name, "drive_file_id": drive_id})
        yield {"type": "progress", "event": {
            "index": len(uploaded), "state": "done", "filename": name, "status": "ok",
        }}
    yield {"type": "result", "delivered": uploaded, "folder_id": folder_id}
