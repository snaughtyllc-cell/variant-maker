# Serverless GPU Runner — Design

**Date:** 2026-06-28
**Status:** Approved (brainstorm) — pending spec review
**Scope:** The GPU compute path for the control plane: a `RunPodServerlessRunner` (drop-in `Runner`) + a streaming worker handler + object storage. Per-second-billed GPU, no rewrite of the existing backend.

---

## 1. Goal

Run variant generation on a **RunPod serverless GPU** (Tier-2 / HQ neural upscale, the proven
RTX-4090 path) instead of local CPU, **without changing the control-plane backend**. The backend
talks to the engine through the `Runner` protocol (Stage-1 seam); this adds a second
implementation, `RunPodServerlessRunner`, alongside `LocalRunner`. Pick which runner the
`JobStore` uses at construction time — nothing else changes. JobStore, SSE, gallery, diagnostics,
and file-serving keep working verbatim because the runner makes remote results look local.

Build entirely against fakes (no cloud account, no cost); real deployment is the final,
user-triggered step with a runbook.

---

## 2. The Runner contract (already exists — must be honored)

From `variant_maker/server/runner.py`:

```
Runner.run(self, source_path: str, *, count: int, out_dir: str, source_id: str,
           on_event: Callable[[VariantEvent], None]) -> SourceResult
```
- `VariantEvent(source_id, index, state, attempt, max_attempts, status, quality, filename)`,
  `state ∈ {rendering, checking, rerolling, done}`.
- `SourceResult(variants: list[VariantResult], manifest_path: str)`;
  `VariantResult(index, filename, status, quality, path)` — `path` is a LOCAL file path.

`RunPodServerlessRunner` MUST satisfy this exactly: forward `VariantEvent`s via `on_event` as
remote progress arrives, and leave the finished variant files on the local filesystem under
`out_dir` (downloaded from object storage) so the existing `Workspace`/file-serving works
unchanged.

---

## 3. Components

### 3.1 Object storage abstraction (`variant_maker/server/storage.py`)
Stateless workers can't share the backend's filesystem, so files move through object storage.

- `ObjectStore` Protocol: `put(key: str, local_path: str) -> None`, `get(key: str, local_path: str) -> None`, `list_prefix(prefix: str) -> list[str]`.
- `S3ObjectStore(endpoint_url, bucket, access_key, secret_key)` — uses `boto3` (S3 API). Works
  with **Cloudflare R2** (recommended: zero egress; default), AWS S3, or RunPod S3 — provider is
  pure config (endpoint + creds). `boto3` is lazy-imported, added under a new `serverless` extra.
- `FakeObjectStore` (in `tests/server/fakes.py`) — in-memory/local-file backed; mirrors `FakeDrive`.
  No network. Lets the runner be fully TDD'd.

### 3.2 RunPod client abstraction (`variant_maker/server/runpod_client.py`)
- `RunPodClient` Protocol: `stream_run(payload: dict) -> Iterator[dict]` — submits a job to the
  serverless endpoint and yields progress/output chunks (RunPod streaming/generator job API; falls
  back to `/run` + status polling internally if streaming is unavailable — hidden behind this seam).
- `HttpRunPodClient(endpoint_id, api_key)` — real impl (lazy `requests`/`httpx`).
- `FakeRunPodClient(plan)` (in `tests/server/fakes.py`) — yields a scripted sequence of progress
  chunks + a final result, no network. Drives the runner's TDD.

### 3.3 `RunPodServerlessRunner` (`variant_maker/server/runpod_runner.py`)
Implements `Runner`. `run(...)`:
1. `store.put(f"inputs/{source_id}/{basename}", source_path)`.
2. `client.stream_run({"input": {source_key, count, preset, platform, quality_mode:"hq", max_regen, source_id}})`.
3. For each yielded **progress** chunk shaped like the engine's `on_event` payload
   (`state/index/attempt/max_attempts/status/quality/filename`), build a `VariantEvent(source_id=…)`
   and call `on_event(...)`.
4. On the final **result** chunk (list of variant records + their object keys), `store.get(...)`
   each variant file into `out_dir`, and fetch `manifest.json` → `out_dir`.
5. Return `SourceResult(variants=[VariantResult(... path=local out_dir path ...)], manifest_path=…)`.

Defaults: `quality_mode="hq"`, `preset="medium"`, `platform="tiktok"`, `max_regen=3` (mirrors
`LocalRunner`, but HQ instead of fast).

### 3.4 Worker handler (`deploy/runpod/cp_handler.py` — NEW; leaves the farm handler untouched)
A RunPod **generator** handler (streams progress). Per job input `{source_key, count, preset,
platform, quality_mode, max_regen, source_id}`:
1. `store.get(source_key, /tmp/in/<file>)`.
2. `pipeline.run(config, on_event=cb)` where `cb(state, **kw)` **yields** a progress chunk for each
   engine event (same payload the runner expects). Runs HQ → Tier-2 upscale + spatial-corruption
   guard, so `corrupt` status is reachable.
3. For each finished variant, `store.put(f"outputs/{source_id}/<filename>", local)`; put
   `manifest.json` too.
4. Yield a final result chunk: variant records (index/filename/status/quality) + their object keys.

The image is the existing **proven** `deploy/runpod/Dockerfile` (Real-ESRGAN + static ffmpeg+libvmaf
+ baked weights); only the handler entrypoint differs (`cp_handler:handler`). The worker imports
`boto3` for storage (add to the image).

### 3.5 Config / wiring
- A small config (extend the server CLI / env): `--runner local|runpod`; when `runpod`, read
  `RUNPOD_ENDPOINT_ID`, `RUNPOD_API_KEY`, and `R2_ENDPOINT/R2_BUCKET/R2_ACCESS_KEY/R2_SECRET_KEY`
  (env or a config file mirroring the farm config pattern). `JobStore` is built with the chosen runner.
- New `serverless` optional-dependency extra: `boto3` (+ `runpod` only needed in the image, not locally).

---

## 4. Status / quality

HQ mode runs the spatial-corruption guard, so the worker can return `status="corrupt"` for a
tile-seam upscale (the guard the farm already enforces). `corrupt` + `best_effort` → Diagnostics +
shortfall, exactly as Stage 1 defined. The `ok`→Gallery mapping is unchanged.

---

## 5. Build approach (TDD, zero cloud cost)

1. `ObjectStore` + `FakeObjectStore` (put/get/list round-trips).
2. `RunPodClient` Protocol + `FakeRunPodClient` (scripted stream).
3. `RunPodServerlessRunner` against the two fakes — assert: source uploaded; progress chunks →
   `VariantEvent`s forwarded with `source_id`; result variants downloaded to `out_dir`;
   `SourceResult` paths are local + exist; status mapping preserved (incl. `corrupt`).
4. `cp_handler` logic factored so its core (download → run+stream → upload → result) is unit-testable
   with `FakeObjectStore` + a monkeypatched `pipeline.run` (no GPU, no ffmpeg).
5. `S3ObjectStore` + `HttpRunPodClient`: thin, lazy-imported, covered by focused tests
   (monkeypatched boto3/http) — no live calls in the suite.

The whole runner + worker is green in CI on CPU with no credentials.

---

## 6. Deployment (final, user-triggered — runbook, not code)

1. Create an R2 bucket + API token (or AWS S3 / RunPod S3); note endpoint, bucket, keys.
2. `docker build -f deploy/runpod/Dockerfile -t <registry>/variant-cp .` (build context = repo root),
   push to a registry. (Image not buildable on this Mac — amd64/NVIDIA.)
3. Create a RunPod **serverless endpoint** from the image with entrypoint `cp_handler:handler`;
   set storage env vars on the endpoint; note the endpoint id.
4. Locally: set `RUNPOD_ENDPOINT_ID`, `RUNPOD_API_KEY`, R2 creds; run
   `variant-server --runner runpod`. Submit a job; verify it streams + variants come back.
5. Rotate the RunPod API key (it was pasted in chat early in the project).

---

## 7. Out of scope

- Multi-source parallelism on the worker (one source per job invocation; backend already loops sources).
- Drive farm changes (separate, parked path; its `handler.py` is untouched).
- Cost autoscaling / endpoint config tuning beyond a working endpoint.
- Frontend (next project after this).

---

## 8. No-rewrite seam summary

`Runner` is the seam. `JobStore(workspace, runner)` takes either `LocalRunner` (CPU/fast) or
`RunPodServerlessRunner` (GPU/hq). Every other backend module — SSE, gallery, diagnostics,
file-serving, models — is untouched. The frontend (built later) is likewise indifferent to which
runner is behind the API.
