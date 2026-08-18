"""Worker core: download source -> pipeline.run (HQ) streaming progress -> upload variants.

`process_job` is a generator that yields the locked progress/result chunks. pipeline.run is
blocking and calls on_event synchronously, so it runs on a background thread and pushes events
into a queue that the generator drains (same threading pattern as JobStore)."""
from __future__ import annotations

import os
import queue
import threading
from typing import Iterator

from .. import pipeline
from .storage import ObjectStore


def _progress_chunk(state: str, kw: dict) -> dict:
    return {"type": "progress", "event": {
        "index": kw.get("index"), "state": state,
        "attempt": kw.get("attempt", 0), "max_attempts": kw.get("max_attempts", 0),
        "status": kw.get("status"), "quality": kw.get("quality"),
        "filename": kw.get("filename"),
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
        "preset": job_input.get("preset", "medium"),
        "platform": job_input.get("platform", "tiktok"),
        "quality_mode": job_input.get("quality_mode", "hq"),
        "max_regen": job_input.get("max_regen", 3), "jobs": 1,
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
        variants.append({"index": v.index, "filename": v.filename,
                         "status": v.status, "quality": v.quality, "key": key})
    manifest_key = f"outputs/{source_id}/manifest.json"
    store.put(manifest_key, os.path.join(out_dir, "manifest.json"))
    yield {"type": "result", "variants": variants, "manifest_key": manifest_key}
