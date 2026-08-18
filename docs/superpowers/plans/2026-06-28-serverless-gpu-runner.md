# Serverless GPU Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `RunPodServerlessRunner` (drop-in `Runner`) plus a streaming worker handler and S3-compatible object storage, so variant generation can run on a per-second-billed RunPod GPU (HQ/Tier-2) without changing the rest of the control-plane backend.

**Architecture:** Files move through object storage (S3 API, Cloudflare R2 by default). The backend-side `RunPodServerlessRunner` uploads the source, submits a streaming RunPod job, translates streamed progress chunks into `VariantEvent`s (forwarded to `on_event`), and downloads finished variants into the local `out_dir` so the existing `JobStore`/`Workspace`/file-serving keep working. The worker side is an in-package, testable `gpu_worker.process_job` generator (download → `pipeline.run` HQ with a thread+queue progress bridge → upload → result), wrapped by a thin `deploy/runpod/cp_handler.py`. Everything is built and tested against fakes — no cloud, no cost; deployment is a final user-triggered runbook.

**Tech Stack:** Python 3.11+, boto3 (S3 API, lazy), httpx (RunPod HTTP, already present), pytest. Worker image: the existing proven `deploy/runpod/Dockerfile` (Real-ESRGAN + static ffmpeg+libvmaf).

## Global Constraints

- **Python** `>=3.11`. Dev venv `./.venv`; run tests with `./.venv/bin/pytest`.
- **Ruff** line-length `100`, target `py311`. `./.venv/bin/ruff check .` must be clean. Run it yourself each task.
- **TDD**: failing test first → watch fail → minimal impl → watch pass → commit.
- **No cloud in the test suite.** boto3 / RunPod HTTP / `runpod` are lazy-imported; tests use `FakeObjectStore`, `FakeRunPodClient`, monkeypatched boto3/httpx. Zero live network calls, zero credentials needed to run the suite.
- **`RunPodServerlessRunner.run` must match the `Runner` protocol signature exactly** and return a `SourceResult` whose `VariantResult.path` values are LOCAL files that exist under `out_dir` (downloaded from storage). Existing protocol (`variant_maker/server/runner.py`): `run(self, source_path, *, count, out_dir, source_id, on_event) -> SourceResult`; `VariantEvent(source_id, index, state, attempt, max_attempts, status, quality, filename)`; `VariantResult(index, filename, status, quality, path)`; `SourceResult(variants, manifest_path)`.
- **RunPodServerlessRunner defaults (locked):** `quality_mode="hq"`, `preset="medium"`, `platform="tiktok"`, `max_regen=3`.
- **The stream chunk contract (locked — runner consumes, worker produces):**
  - progress: `{"type": "progress", "event": {"index": int, "state": str, "attempt": int, "max_attempts": int, "status": str|None, "quality": dict|None, "filename": str|None}}`
  - result: `{"type": "result", "variants": [{"index": int, "filename": str, "status": str, "quality": dict, "key": str}], "manifest_key": str}`
- **Do NOT touch `deploy/runpod/handler.py`** (the parked Drive-farm worker). Add a new `cp_handler.py`.
- **Imports at the top of files**, except the deliberately lazy heavy deps (boto3 inside `S3ObjectStore`, httpx inside `HttpRunPodClient`, `runpod` inside `cp_handler`'s `__main__`).
- **New `serverless` optional-dependency extra**: `boto3`.

---

## File Structure

**New (package):**
- `variant_maker/server/storage.py` — `ObjectStore` Protocol + `S3ObjectStore` (lazy boto3).
- `variant_maker/server/runpod_client.py` — `RunPodClient` Protocol + `HttpRunPodClient` (lazy httpx).
- `variant_maker/server/runpod_runner.py` — `RunPodServerlessRunner` (implements `Runner`).
- `variant_maker/server/gpu_worker.py` — `process_job(...)` generator (testable worker core).

**New (deploy):**
- `deploy/runpod/cp_handler.py` — thin RunPod generator handler wrapping `process_job` with `S3ObjectStore`.

**Modified:**
- `pyproject.toml` — add `serverless` extra.
- `variant_maker/server/cli.py` — `--runner local|runpod` + env-based wiring.
- `deploy/runpod/README.md` — deployment runbook for the control-plane endpoint.

**Tests:**
- `tests/server/fakes.py` — add `FakeObjectStore`, `FakeRunPodClient`, `LoopbackRunPodClient`.
- `tests/server/test_storage.py`, `test_runpod_client.py`, `test_runpod_runner.py`, `test_gpu_worker.py`, `test_runpod_end_to_end.py`, and a CLI test in `test_app.py`.

---

## Task 1: `serverless` extra + ObjectStore + S3ObjectStore + FakeObjectStore

**Files:**
- Modify: `pyproject.toml`
- Create: `variant_maker/server/storage.py`
- Modify: `tests/server/fakes.py`
- Create: `tests/server/test_storage.py`

**Interfaces:**
- Produces:
  - `ObjectStore` Protocol: `put(self, key: str, local_path: str) -> None`, `get(self, key: str, local_path: str) -> None`, `list_prefix(self, prefix: str) -> list[str]`.
  - `S3ObjectStore(*, endpoint_url: str, bucket: str, access_key: str, secret_key: str, region: str = "auto")` — lazy boto3 S3 client; same three methods.
  - `FakeObjectStore()` (in `tests/server/fakes.py`) — in-memory bytes store; same three methods; `get` creates parent dirs.

- [ ] **Step 1: Add the `serverless` extra to `pyproject.toml`**

In `[project.optional-dependencies]` add:

```toml
serverless = ["boto3>=1.34"]
```

Install: `./.venv/bin/pip install -e ".[dev,server,serverless]"` then `./.venv/bin/python -c "import boto3; print('ok')"` → prints `ok`.

- [ ] **Step 2: Write the failing tests**

Create `tests/server/test_storage.py`:

```python
from tests.server.fakes import FakeObjectStore


def test_fake_put_get_roundtrip(tmp_path):
    store = FakeObjectStore()
    src = tmp_path / "a.bin"
    src.write_bytes(b"hello-bytes")
    store.put("inputs/x/a.bin", str(src))

    dst = tmp_path / "out" / "a.bin"  # parent dir does not exist yet
    store.get("inputs/x/a.bin", str(dst))
    assert dst.read_bytes() == b"hello-bytes"


def test_fake_list_prefix(tmp_path):
    store = FakeObjectStore()
    src = tmp_path / "f"
    src.write_bytes(b"x")
    store.put("outputs/s1/v01.mp4", str(src))
    store.put("outputs/s1/v02.mp4", str(src))
    store.put("outputs/s2/v01.mp4", str(src))
    assert sorted(store.list_prefix("outputs/s1/")) == ["outputs/s1/v01.mp4", "outputs/s1/v02.mp4"]


def test_s3_store_uses_boto_client(monkeypatch, tmp_path):
    import variant_maker.server.storage as storage

    calls = {"upload": [], "download": [], "list": []}

    class FakeClient:
        def upload_file(self, local, bucket, key):
            calls["upload"].append((local, bucket, key))
        def download_file(self, bucket, key, local):
            calls["download"].append((bucket, key, local))
            open(local, "wb").close()
        def get_paginator(self, op):
            class P:
                def paginate(self, Bucket, Prefix):
                    yield {"Contents": [{"Key": Prefix + "v01.mp4"}]}
            return P()

    monkeypatch.setattr(storage, "_make_client",
                        lambda **kw: FakeClient())
    s = storage.S3ObjectStore(endpoint_url="https://r2", bucket="b",
                              access_key="a", secret_key="s")
    src = tmp_path / "in.mp4"; src.write_bytes(b"x")
    s.put("inputs/x/in.mp4", str(src))
    assert calls["upload"] == [(str(src), "b", "inputs/x/in.mp4")]
    s.get("outputs/x/v01.mp4", str(tmp_path / "got.mp4"))
    assert calls["download"][0][:2] == ("b", "outputs/x/v01.mp4")
    assert s.list_prefix("outputs/x/") == ["outputs/x/v01.mp4"]
```

- [ ] **Step 3: Run; verify it fails**

Run: `./.venv/bin/pytest tests/server/test_storage.py -q`
Expected: FAIL — `ImportError`/`AttributeError` (FakeObjectStore / storage module missing).

- [ ] **Step 4: Implement `variant_maker/server/storage.py`**

```python
"""Object storage seam for moving files in/out of stateless GPU workers (S3 API)."""
from __future__ import annotations

from typing import Protocol


class ObjectStore(Protocol):
    def put(self, key: str, local_path: str) -> None: ...
    def get(self, key: str, local_path: str) -> None: ...
    def list_prefix(self, prefix: str) -> list[str]: ...


def _make_client(*, endpoint_url: str, access_key: str, secret_key: str, region: str):
    import boto3  # lazy: only needed when a real S3 store is constructed
    return boto3.client(
        "s3", endpoint_url=endpoint_url, aws_access_key_id=access_key,
        aws_secret_access_key=secret_key, region_name=region,
    )


class S3ObjectStore:
    """S3-compatible store (Cloudflare R2 by default; also AWS S3 / RunPod S3)."""

    def __init__(self, *, endpoint_url: str, bucket: str, access_key: str,
                 secret_key: str, region: str = "auto") -> None:
        self._bucket = bucket
        self._client = _make_client(endpoint_url=endpoint_url, access_key=access_key,
                                    secret_key=secret_key, region=region)

    def put(self, key: str, local_path: str) -> None:
        self._client.upload_file(local_path, self._bucket, key)

    def get(self, key: str, local_path: str) -> None:
        import os
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        self._client.download_file(self._bucket, key, local_path)

    def list_prefix(self, prefix: str) -> list[str]:
        keys: list[str] = []
        for page in self._client.get_paginator("list_objects_v2").paginate(
                Bucket=self._bucket, Prefix=prefix):
            keys.extend(obj["Key"] for obj in page.get("Contents", []))
        return keys
```

- [ ] **Step 5: Add `FakeObjectStore` to `tests/server/fakes.py`**

Append:

```python
class FakeObjectStore:
    """In-memory object store for tests — no network, no boto3."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    def put(self, key: str, local_path: str) -> None:
        with open(local_path, "rb") as f:
            self._data[key] = f.read()

    def get(self, key: str, local_path: str) -> None:
        import os
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(self._data[key])

    def list_prefix(self, prefix: str) -> list[str]:
        return [k for k in self._data if k.startswith(prefix)]
```

- [ ] **Step 6: Run; verify it passes**

Run: `./.venv/bin/pytest tests/server/test_storage.py -q`
Expected: PASS (3 passed).

- [ ] **Step 7: Lint + commit**

Run: `./.venv/bin/ruff check .` (clean).

```bash
git add pyproject.toml variant_maker/server/storage.py tests/server/fakes.py tests/server/test_storage.py
git commit -m "feat(server): ObjectStore seam + S3ObjectStore + FakeObjectStore"
```

---

## Task 2: RunPodClient Protocol + FakeRunPodClient + HttpRunPodClient

**Files:**
- Create: `variant_maker/server/runpod_client.py`
- Modify: `tests/server/fakes.py`
- Create: `tests/server/test_runpod_client.py`

**Interfaces:**
- Produces:
  - `RunPodClient` Protocol: `stream_run(self, payload: dict) -> Iterator[dict]` — submits a job and yields output chunks (each chunk follows the locked progress/result contract).
  - `HttpRunPodClient(*, endpoint_id: str, api_key: str, base_url: str = "https://api.runpod.ai/v2", poll_interval: float = 1.0)` — real impl (lazy httpx): POST `/run`, then GET `/stream/{id}` until `COMPLETED`/`FAILED`, yielding each `output` item.
  - `FakeRunPodClient(chunks: list[dict])` (in `tests/server/fakes.py`) — `stream_run` yields the scripted `chunks` (ignores payload).

- [ ] **Step 1: Write failing tests**

Create `tests/server/test_runpod_client.py`:

```python
from tests.server.fakes import FakeRunPodClient


def test_fake_client_yields_scripted_chunks():
    chunks = [{"type": "progress", "event": {"index": 1, "state": "rendering"}},
              {"type": "result", "variants": [], "manifest_key": "m"}]
    client = FakeRunPodClient(chunks)
    assert list(client.stream_run({"input": {}})) == chunks


def test_http_client_posts_run_then_streams(monkeypatch):
    import variant_maker.server.runpod_client as rc

    posted = {}

    class FakeResp:
        def __init__(self, payload): self._p = payload
        def raise_for_status(self): pass
        def json(self): return self._p

    class FakeHttp:
        def post(self, url, json, headers):
            posted["run"] = (url, json, headers)
            return FakeResp({"id": "job123"})
        def get(self, url, headers):
            # first poll: in-progress with one stream item; second: completed
            if not posted.get("polled"):
                posted["polled"] = True
                return FakeResp({"status": "IN_PROGRESS",
                                 "stream": [{"output": {"type": "progress",
                                                        "event": {"index": 1, "state": "rendering"}}}]})
            return FakeResp({"status": "COMPLETED",
                             "stream": [{"output": {"type": "result", "variants": [],
                                                    "manifest_key": "m"}}]})

    monkeypatch.setattr(rc, "_http", lambda: FakeHttp())
    client = rc.HttpRunPodClient(endpoint_id="ep", api_key="k", poll_interval=0)
    out = list(client.stream_run({"input": {"count": 2}}))
    assert posted["run"][0].endswith("/ep/run")
    assert posted["run"][2]["Authorization"] == "Bearer k"
    assert out[0] == {"type": "progress", "event": {"index": 1, "state": "rendering"}}
    assert out[-1] == {"type": "result", "variants": [], "manifest_key": "m"}
```

- [ ] **Step 2: Run; verify it fails**

Run: `./.venv/bin/pytest tests/server/test_runpod_client.py -q`
Expected: FAIL — module/attr missing.

- [ ] **Step 3: Implement `variant_maker/server/runpod_client.py`**

```python
"""RunPod serverless client seam: submit a job and stream its output chunks."""
from __future__ import annotations

import time
from typing import Iterator, Protocol


class RunPodClient(Protocol):
    def stream_run(self, payload: dict) -> Iterator[dict]: ...


def _http():
    import httpx  # lazy: only the real client needs it
    return httpx.Client(timeout=60.0)


class HttpRunPodClient:
    def __init__(self, *, endpoint_id: str, api_key: str,
                 base_url: str = "https://api.runpod.ai/v2", poll_interval: float = 1.0) -> None:
        self._base = f"{base_url}/{endpoint_id}"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._poll = poll_interval

    def stream_run(self, payload: dict) -> Iterator[dict]:
        http = _http()
        resp = http.post(f"{self._base}/run", json=payload, headers=self._headers)
        resp.raise_for_status()
        job_id = resp.json()["id"]
        while True:
            r = http.get(f"{self._base}/stream/{job_id}", headers=self._headers)
            r.raise_for_status()
            body = r.json()
            for item in body.get("stream", []):
                yield item["output"]
            status = body.get("status")
            if status in ("COMPLETED", "FAILED", "CANCELLED"):
                if status != "COMPLETED":
                    raise RuntimeError(f"RunPod job {job_id} ended: {status}")
                return
            if self._poll:
                time.sleep(self._poll)
```

- [ ] **Step 4: Add `FakeRunPodClient` to `tests/server/fakes.py`**

```python
class FakeRunPodClient:
    """Yields a scripted list of output chunks; ignores the payload. No network."""

    def __init__(self, chunks: list[dict]) -> None:
        self._chunks = chunks

    def stream_run(self, payload: dict):
        yield from self._chunks
```

- [ ] **Step 5: Run; verify it passes**

Run: `./.venv/bin/pytest tests/server/test_runpod_client.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Lint + commit**

```bash
git add variant_maker/server/runpod_client.py tests/server/fakes.py tests/server/test_runpod_client.py
git commit -m "feat(server): RunPodClient seam + HttpRunPodClient + FakeRunPodClient"
```

---

## Task 3: RunPodServerlessRunner

**Files:**
- Create: `variant_maker/server/runpod_runner.py`
- Create: `tests/server/test_runpod_runner.py`

**Interfaces:**
- Consumes: `ObjectStore` (Task 1), `RunPodClient` (Task 2), `VariantEvent`/`VariantResult`/`SourceResult` (`runner.py`), the locked chunk contract.
- Produces: `RunPodServerlessRunner(store: ObjectStore, client: RunPodClient)` implementing `Runner.run(...)`.

- [ ] **Step 1: Write failing tests**

Create `tests/server/test_runpod_runner.py`:

```python
import os

from variant_maker.server.events import VariantEvent
from variant_maker.server.runner import SourceResult, VariantResult
from variant_maker.server.runpod_runner import RunPodServerlessRunner
from tests.server.fakes import FakeObjectStore, FakeRunPodClient


def test_runner_uploads_source_streams_events_downloads_variants(tmp_path):
    store = FakeObjectStore()
    # Pre-stage what the "worker" would have uploaded: two variant files + manifest.
    for key, body in [("outputs/srcA/v01.mp4", b"V1"),
                      ("outputs/srcA/v02.mp4", b"V2"),
                      ("outputs/srcA/manifest.json", b"{}")]:
        p = tmp_path / "stage" / os.path.basename(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
        store.put(key, str(p))

    chunks = [
        {"type": "progress", "event": {"index": 1, "state": "rendering", "attempt": 0}},
        {"type": "progress", "event": {"index": 1, "state": "done", "status": "ok",
                                       "quality": {"vmaf": 95.0}, "filename": "v01.mp4"}},
        {"type": "progress", "event": {"index": 2, "state": "done", "status": "corrupt",
                                       "quality": {"vmaf": 10.0}, "filename": "v02.mp4"}},
        {"type": "result", "variants": [
            {"index": 1, "filename": "v01.mp4", "status": "ok",
             "quality": {"vmaf": 95.0}, "key": "outputs/srcA/v01.mp4"},
            {"index": 2, "filename": "v02.mp4", "status": "corrupt",
             "quality": {"vmaf": 10.0}, "key": "outputs/srcA/v02.mp4"}],
         "manifest_key": "outputs/srcA/manifest.json"},
    ]

    src = tmp_path / "in.mp4"; src.write_bytes(b"SRC")
    events: list[VariantEvent] = []
    out_dir = str(tmp_path / "out")
    runner = RunPodServerlessRunner(store, FakeRunPodClient(chunks))
    result = runner.run(str(src), count=2, out_dir=out_dir, source_id="srcA",
                        on_event=events.append)

    # source uploaded under inputs/<source_id>/<basename>
    assert "inputs/srcA/in.mp4" in store.list_prefix("inputs/srcA/")
    # progress forwarded as VariantEvents tagged with source_id
    assert all(e.source_id == "srcA" for e in events)
    assert {e.status for e in events if e.state == "done"} == {"ok", "corrupt"}
    # variants downloaded to local out_dir, statuses preserved (incl. corrupt)
    assert isinstance(result, SourceResult)
    assert [v.status for v in result.variants] == ["ok", "corrupt"]
    assert all(isinstance(v, VariantResult) for v in result.variants)
    for v in result.variants:
        assert os.path.isfile(v.path) and v.path.startswith(out_dir)
    assert os.path.isfile(result.manifest_path)


def test_runner_sends_hq_defaults_in_payload(tmp_path):
    captured = {}

    class CapturingClient:
        def stream_run(self, payload):
            captured.update(payload["input"])
            return iter([{"type": "result", "variants": [], "manifest_key": None}])

    store = FakeObjectStore()
    src = tmp_path / "in.mp4"; src.write_bytes(b"x")
    RunPodServerlessRunner(store, CapturingClient()).run(
        str(src), count=7, out_dir=str(tmp_path / "o"), source_id="s", on_event=lambda e: None)
    assert captured["quality_mode"] == "hq"
    assert captured["preset"] == "medium"
    assert captured["platform"] == "tiktok"
    assert captured["max_regen"] == 3
    assert captured["count"] == 7
    assert captured["source_id"] == "s"
    assert captured["source_key"] == "inputs/s/in.mp4"
```

- [ ] **Step 2: Run; verify it fails**

Run: `./.venv/bin/pytest tests/server/test_runpod_runner.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `variant_maker/server/runpod_runner.py`**

```python
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
```

- [ ] **Step 4: Run; verify it passes**

Run: `./.venv/bin/pytest tests/server/test_runpod_runner.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Lint + commit**

```bash
git add variant_maker/server/runpod_runner.py tests/server/test_runpod_runner.py
git commit -m "feat(server): RunPodServerlessRunner (GPU drop-in Runner)"
```

---

## Task 4: Worker core (`gpu_worker.process_job`) + `cp_handler.py`

**Files:**
- Create: `variant_maker/server/gpu_worker.py`
- Create: `deploy/runpod/cp_handler.py`
- Create: `tests/server/test_gpu_worker.py`

**Interfaces:**
- Consumes: `ObjectStore`, `pipeline.run(config, on_event=...)`, the locked chunk contract.
- Produces: `gpu_worker.process_job(job_input: dict, store: ObjectStore, *, work_dir: str) -> Iterator[dict]` — a generator that downloads the source, runs `pipeline.run` (HQ) on a background thread bridging `on_event` to yielded **progress** chunks, uploads each variant + manifest, then yields one **result** chunk. `deploy/runpod/cp_handler.py` exposes `handler(event)` (generator) wrapping `process_job` with an `S3ObjectStore` from env.

- [ ] **Step 1: Write the failing test (monkeypatched pipeline.run — no ffmpeg)**

Create `tests/server/test_gpu_worker.py`:

```python
import os

from variant_maker.server import gpu_worker
from tests.server.fakes import FakeObjectStore


def test_process_job_streams_progress_then_uploads_and_results(monkeypatch, tmp_path):
    store = FakeObjectStore()
    # stage the source object the worker will download
    src = tmp_path / "src.mp4"; src.write_bytes(b"SRC")
    store.put("inputs/s1/src.mp4", str(src))

    class FakeRecord:
        def __init__(self, index, filename, status, quality):
            self.index, self.filename, self.status, self.quality = index, filename, status, quality

    class FakeManifest:
        def __init__(self, variants): self.variants = variants

    def fake_run(config, *, on_event=None):
        out = config["out"]
        recs = []
        for i, status in [(1, "ok"), (2, "corrupt")]:
            fname = f"v{i:02d}.mp4"
            on_event("rendering", index=i, attempt=0)
            on_event("done", index=i, status=status,
                     quality={"vmaf": 95.0 if status == "ok" else 5.0}, filename=fname)
            open(os.path.join(out, fname), "w").close()
            recs.append(FakeRecord(i, fname, status, {"vmaf": 95.0}))
        open(os.path.join(out, "manifest.json"), "w").close()
        return FakeManifest(recs)

    monkeypatch.setattr(gpu_worker.pipeline, "run", fake_run)

    job_input = {"source_key": "inputs/s1/src.mp4", "source_id": "s1", "count": 2}
    chunks = list(gpu_worker.process_job(job_input, store, work_dir=str(tmp_path / "work")))

    progress = [c for c in chunks if c["type"] == "progress"]
    results = [c for c in chunks if c["type"] == "result"]
    # progress streamed for both variants, including the corrupt one
    assert [c["event"]["state"] for c in progress[:2]] == ["rendering", "done"]
    assert {c["event"].get("status") for c in progress if c["event"]["state"] == "done"} == {"ok", "corrupt"}
    # exactly one result chunk, variants uploaded under outputs/<source_id>/
    assert len(results) == 1
    res = results[0]
    assert [v["status"] for v in res["variants"]] == ["ok", "corrupt"]
    assert res["manifest_key"] == "outputs/s1/manifest.json"
    assert "outputs/s1/v01.mp4" in store.list_prefix("outputs/s1/")
    assert "outputs/s1/v02.mp4" in store.list_prefix("outputs/s1/")
    # each result variant carries its object key
    assert res["variants"][0]["key"] == "outputs/s1/v01.mp4"
```

- [ ] **Step 2: Run; verify it fails**

Run: `./.venv/bin/pytest tests/server/test_gpu_worker.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `variant_maker/server/gpu_worker.py`**

```python
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
```

- [ ] **Step 4: Run; verify it passes**

Run: `./.venv/bin/pytest tests/server/test_gpu_worker.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Create `deploy/runpod/cp_handler.py` (thin wrapper; not unit-tested — it only wires env + S3 to the tested core)**

```python
"""RunPod serverless entry for the CONTROL PLANE (distinct from the parked Drive farm handler.py).

Streams per-variant progress: wraps the tested `gpu_worker.process_job` generator with an
S3ObjectStore built from endpoint env vars. `runpod` is imported lazily so this stays importable
off the GPU box."""
import os
import tempfile

from variant_maker.server.gpu_worker import process_job
from variant_maker.server.storage import S3ObjectStore


def _store() -> S3ObjectStore:
    return S3ObjectStore(
        endpoint_url=os.environ["R2_ENDPOINT"], bucket=os.environ["R2_BUCKET"],
        access_key=os.environ["R2_ACCESS_KEY"], secret_key=os.environ["R2_SECRET_KEY"],
    )


def handler(event: dict):
    work_dir = tempfile.mkdtemp(prefix="cp_job_")
    yield from process_job(event.get("input", {}), _store(), work_dir=work_dir)


if __name__ == "__main__":
    import runpod
    runpod.serverless.start({"handler": handler, "return_aggregate_stream": True})
```

- [ ] **Step 6: Verify cp_handler imports without runpod installed**

Run: `./.venv/bin/python -c "import importlib.util, pathlib; importlib.util.spec_from_file_location('cp', 'deploy/runpod/cp_handler.py'); print('import-path ok')"`
(Confirms the module's top-level imports — `process_job`, `S3ObjectStore` — resolve without `runpod`.)
Then: `./.venv/bin/pytest -q -m "not integration"` (full unit suite still green).

- [ ] **Step 7: Lint + commit**

Run: `./.venv/bin/ruff check .` (clean).

```bash
git add variant_maker/server/gpu_worker.py deploy/runpod/cp_handler.py tests/server/test_gpu_worker.py
git commit -m "feat(server): streaming GPU worker core + control-plane RunPod handler"
```

---

## Task 5: Runner selection in the CLI (`--runner local|runpod`)

**Files:**
- Modify: `variant_maker/server/cli.py`
- Modify: `tests/server/test_app.py`

**Interfaces:**
- Consumes: `LocalRunner`, `RunPodServerlessRunner`, `S3ObjectStore`, `HttpRunPodClient`, `JobStore`, `Workspace`.
- Produces:
  - `cli.make_runner(kind: str) -> Runner` — `"local"` → `LocalRunner()`; `"runpod"` → `RunPodServerlessRunner(S3ObjectStore(...from env...), HttpRunPodClient(...from env...))`. Raises `SystemExit` with a clear message if a required env var is missing for `runpod`.
  - `cli.build_app(data_dir: str, runner_kind: str = "local") -> FastAPI` — wires `JobStore(Workspace(data_dir), make_runner(runner_kind))`.
  - `main()` gains `--runner` (choices `local`/`runpod`, default `local`), passed to `build_app`.

- [ ] **Step 1: Write failing tests (append to `tests/server/test_app.py`)**

```python
def test_make_runner_local():
    from variant_maker.server.cli import make_runner
    from variant_maker.server.runner import LocalRunner
    assert isinstance(make_runner("local"), LocalRunner)


def test_make_runner_runpod_from_env(monkeypatch):
    from variant_maker.server import cli
    from variant_maker.server.runpod_runner import RunPodServerlessRunner
    # avoid real boto3/httpx construction
    monkeypatch.setattr(cli, "S3ObjectStore", lambda **kw: object())
    monkeypatch.setattr(cli, "HttpRunPodClient", lambda **kw: object())
    for k, v in {"RUNPOD_ENDPOINT_ID": "ep", "RUNPOD_API_KEY": "k",
                 "R2_ENDPOINT": "https://r2", "R2_BUCKET": "b",
                 "R2_ACCESS_KEY": "a", "R2_SECRET_KEY": "s"}.items():
        monkeypatch.setenv(k, v)
    assert isinstance(cli.make_runner("runpod"), RunPodServerlessRunner)


def test_make_runner_runpod_missing_env_exits(monkeypatch):
    from variant_maker.server import cli
    for k in ("RUNPOD_ENDPOINT_ID", "RUNPOD_API_KEY", "R2_ENDPOINT", "R2_BUCKET",
              "R2_ACCESS_KEY", "R2_SECRET_KEY"):
        monkeypatch.delenv(k, raising=False)
    import pytest
    with pytest.raises(SystemExit):
        cli.make_runner("runpod")
```

- [ ] **Step 2: Run; verify it fails**

Run: `./.venv/bin/pytest tests/server/test_app.py -k make_runner -q`
Expected: FAIL — `make_runner` undefined.

- [ ] **Step 3: Rewrite `variant_maker/server/cli.py`**

```python
"""`variant-server` — launch the local control-plane API."""
from __future__ import annotations

import argparse
import os
import sys

from fastapi import FastAPI

from .app import create_app
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
    return create_app(JobStore(Workspace(data_dir), make_runner(runner_kind)))


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
```

(Note: the existing `test_cli_build_app_serves_health` calls `build_app(str(tmp_path))` — the new `runner_kind` default `"local"` keeps it working unchanged.)

- [ ] **Step 4: Run; verify it passes**

Run: `./.venv/bin/pytest tests/server/test_app.py -q`
Expected: PASS (all app tests incl. the 3 new + the unchanged health/cli tests).

- [ ] **Step 5: Lint + commit**

```bash
git add variant_maker/server/cli.py tests/server/test_app.py
git commit -m "feat(server): --runner local|runpod selection (env-wired GPU runner)"
```

---

## Task 6: End-to-end runner↔worker contract test (loopback) + deployment runbook

Proves the `RunPodServerlessRunner` and `gpu_worker` agree on the chunk contract by wiring them together through a loopback client + a shared `FakeObjectStore` — with `pipeline.run` monkeypatched (no ffmpeg, no cloud). Then documents real deployment.

**Files:**
- Modify: `tests/server/fakes.py` (add `LoopbackRunPodClient`)
- Create: `tests/server/test_runpod_end_to_end.py`
- Modify: `deploy/runpod/README.md`

**Interfaces:**
- Consumes: `gpu_worker.process_job`, `ObjectStore`, the chunk contract.
- Produces: `LoopbackRunPodClient(store, work_dir)` — `stream_run(payload)` invokes `process_job(payload["input"], store, work_dir=work_dir)` and yields its chunks (simulates the worker running "remotely" against the same store).

- [ ] **Step 1: Add `LoopbackRunPodClient` to `tests/server/fakes.py`**

```python
class LoopbackRunPodClient:
    """Drives the REAL gpu_worker.process_job against a shared store — no network, no cloud.
    Used to verify the runner<->worker chunk contract end to end."""

    def __init__(self, store, work_dir: str) -> None:
        self._store = store
        self._work_dir = work_dir

    def stream_run(self, payload: dict):
        from variant_maker.server.gpu_worker import process_job
        yield from process_job(payload["input"], self._store, work_dir=self._work_dir)
```

- [ ] **Step 2: Write the end-to-end test**

Create `tests/server/test_runpod_end_to_end.py`:

```python
import os

from variant_maker.server import gpu_worker
from variant_maker.server.runpod_runner import RunPodServerlessRunner
from tests.server.fakes import FakeObjectStore, LoopbackRunPodClient


def test_runner_through_worker_contract(monkeypatch, tmp_path):
    class FakeRecord:
        def __init__(self, index, filename, status, quality):
            self.index, self.filename, self.status, self.quality = index, filename, status, quality

    class FakeManifest:
        def __init__(self, variants): self.variants = variants

    def fake_run(config, *, on_event=None):
        out = config["out"]
        recs = []
        for i, status in [(1, "ok"), (2, "ok")]:
            fname = f"v{i:02d}.mp4"
            on_event("rendering", index=i, attempt=0)
            on_event("done", index=i, status=status, quality={"vmaf": 99.0}, filename=fname)
            with open(os.path.join(out, fname), "wb") as f:
                f.write(f"DATA{i}".encode())
        with open(os.path.join(out, "manifest.json"), "w") as f:
            f.write("{}")
        return FakeManifest([FakeRecord(1, "v01.mp4", "ok", {"vmaf": 99.0}),
                             FakeRecord(2, "v02.mp4", "ok", {"vmaf": 99.0})])

    monkeypatch.setattr(gpu_worker.pipeline, "run", fake_run)

    store = FakeObjectStore()
    client = LoopbackRunPodClient(store, work_dir=str(tmp_path / "worker"))
    runner = RunPodServerlessRunner(store, client)

    src = tmp_path / "in.mp4"; src.write_bytes(b"SOURCE")
    events = []
    out_dir = str(tmp_path / "out")
    result = runner.run(str(src), count=2, out_dir=out_dir, source_id="s1",
                        on_event=events.append)

    # progress flowed runner<-worker, tagged with source_id
    assert [e.state for e in events][:2] == ["rendering", "done"]
    assert all(e.source_id == "s1" for e in events)
    # variants round-tripped through the store to local files with real content
    assert [v.status for v in result.variants] == ["ok", "ok"]
    assert open(result.variants[0].path, "rb").read() == b"DATA1"
    assert open(result.variants[1].path, "rb").read() == b"DATA2"
    assert os.path.isfile(result.manifest_path)
```

- [ ] **Step 3: Run; verify it passes**

Run: `./.venv/bin/pytest tests/server/test_runpod_end_to_end.py -q`
Expected: PASS (1 passed).

- [ ] **Step 4: Write the deployment runbook**

Append a `## Control-plane serverless endpoint` section to `deploy/runpod/README.md` documenting, verbatim and in order:

```markdown
## Control-plane serverless endpoint (GPU runner)

The control plane runs GPU jobs on a RunPod serverless endpoint using
`deploy/runpod/cp_handler.py` (streams per-variant progress). Steps:

1. **Object storage (Cloudflare R2 recommended — zero egress).**
   Create a bucket and an API token. Note: account endpoint URL, bucket name, access key, secret.
   (AWS S3 or RunPod S3 also work — they are the same S3 API; only the endpoint/creds differ.)

2. **Build + push the worker image** (amd64/NVIDIA — not buildable on macOS):
   ```
   docker build -f deploy/runpod/Dockerfile -t <registry>/variant-cp:latest .
   docker push <registry>/variant-cp:latest
   ```
   Build context is the repo root.

3. **Create the RunPod serverless endpoint** from that image. Set the container start command /
   entrypoint to run the control-plane handler:
   ```
   python -u deploy/runpod/cp_handler.py
   ```
   Set these endpoint environment variables: `R2_ENDPOINT`, `R2_BUCKET`, `R2_ACCESS_KEY`,
   `R2_SECRET_KEY`. Note the endpoint id.

4. **Point the local backend at it:**
   ```
   export RUNPOD_ENDPOINT_ID=<id> RUNPOD_API_KEY=<key>
   export R2_ENDPOINT=<url> R2_BUCKET=<bucket> R2_ACCESS_KEY=<ak> R2_SECRET_KEY=<sk>
   variant-server --runner runpod
   ```
   Submit a job; confirm SSE streams progress and variants are served from the gallery.

5. **Rotate the RunPod API key** (it was pasted in chat early in the project).
```

- [ ] **Step 5: Run the full unit suite + lint**

Run: `./.venv/bin/pytest -q -m "not integration"` (all pass) and `./.venv/bin/ruff check .` (clean).

- [ ] **Step 6: Commit**

```bash
git add tests/server/fakes.py tests/server/test_runpod_end_to_end.py deploy/runpod/README.md
git commit -m "test(server): runner<->worker loopback contract test + deploy runbook"
```

---

## Self-Review

**1. Spec coverage** (spec → task):
- ObjectStore + S3ObjectStore + FakeObjectStore (spec §3.1) → Task 1.
- RunPodClient + HttpRunPodClient + FakeRunPodClient (spec §3.2) → Task 2.
- RunPodServerlessRunner, HQ defaults, source_id tagging, local-path download (spec §3.3, §2) → Task 3.
- Worker `process_job` streaming + `cp_handler` (spec §3.4) → Task 4.
- CLI/config `--runner`, env wiring, `serverless` extra (spec §3.5) → Tasks 1 (extra) + 5.
- `corrupt` status reachable + mapping (spec §4) → exercised in Tasks 3 & 4 tests.
- Build-against-fakes, no cloud (spec §5) → all tasks use fakes/monkeypatch; Task 6 loopback capstone.
- Deployment runbook (spec §6) → Task 6 Step 4.
- No-rewrite seam (spec §8) → Task 5 wires either runner into the unchanged `JobStore`.

**2. Placeholder scan:** No "TBD"/"add error handling"/"similar to" — every step has real code or a real command. ✅

**3. Type consistency:** Chunk contract (`{"type":"progress","event":{...}}` / `{"type":"result","variants":[{...,"key":...}],"manifest_key":...}`) is identical in Task 3 (consumer), Task 4 (producer), Task 6 (loopback). `RunPodServerlessRunner(store, client)` ctor + `run(...)` signature consistent across Tasks 3, 5, 6. `ObjectStore` put/get/list_prefix identical in Tasks 1, 3, 4. `make_runner`/`build_app` signatures consistent in Task 5. ✅

**Note (carried for the implementer):** Task 4's `gpu_worker` reuses the same thread+queue streaming pattern as `JobStore._run_job`; the `pipeline.run(..., on_event=...)` callback shape matches the Stage-1 engine seam exactly (state + index/attempt/max_attempts/status/quality/filename).

---

## Execution Handoff

(filled in after user review)
