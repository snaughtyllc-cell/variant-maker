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
from .runner import (
    DEFAULT_PLATFORM,
    DEFAULT_PRESET,
    MAX_REGEN,
    MIN_BITS_VS_PEERS,
    UNIQ_STRENGTHS,
    UNIQUENESS_TARGET,
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
    }}


def process_job(job_input: dict, store: ObjectStore, *, work_dir: str) -> Iterator[dict]:
    source_key = job_input["source_key"]
    source_id = job_input["source_id"]
    count = job_input["count"]
    basename = os.path.basename(source_key)

    in_path = os.path.join(work_dir, "in", basename)
    store.get(source_key, in_path)
    out_dir = os.path.join(work_dir, "out")
    os.makedirs(out_dir, exist_ok=True)

    config = {
        "input": in_path, "out": out_dir, "count": count,
        "preset": job_input.get("preset", DEFAULT_PRESET),
        "platform": job_input.get("platform", DEFAULT_PLATFORM),
        "quality_mode": job_input.get("quality_mode", "hq"),
        "max_regen": job_input.get("max_regen", MAX_REGEN), "jobs": 1,
        "uniqueness_target": job_input.get("uniqueness_target", UNIQUENESS_TARGET),
        "uniq_strengths": job_input.get("uniq_strengths", list(UNIQ_STRENGTHS)),
        "min_bits_vs_peers": job_input.get("min_bits_vs_peers", MIN_BITS_VS_PEERS),
        "allow_creative_escalate": job_input.get("allow_creative_escalate", True),
    }

    q: queue.Queue = queue.Queue()
    DONE = object()
    holder: dict = {}

    def emit(state: str, **kw) -> None:
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
        key = f"outputs/{source_id}/{v.filename}"
        store.put(key, os.path.join(out_dir, v.filename))
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
        })
    manifest_key = f"outputs/{source_id}/manifest.json"
    store.put(manifest_key, os.path.join(out_dir, "manifest.json"))
    yield {"type": "result", "variants": variants, "manifest_key": manifest_key}
