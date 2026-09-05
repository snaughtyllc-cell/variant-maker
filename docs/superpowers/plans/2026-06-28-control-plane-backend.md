# Control-Plane Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the local FastAPI backend that drives the variant-maker engine, streams live per-variant progress over SSE, and serves variants/manifests — the control plane's server half, built against a `Runner` seam so a GPU runner drops in later with no rewrite.

**Architecture:** A new `variant_maker/server/` subpackage (mirrors the existing `farm/` subpackage + extra pattern). The engine gains an optional `on_event` progress callback. A `Runner` protocol abstracts "render one source video into N variants"; `LocalRunner` wraps `pipeline.run` in-process (CPU, fast tier). A `JobStore` runs jobs in a background thread, records an in-memory event log per job, and exposes job/gallery/diagnostics state. FastAPI routes expose the contract the Next.js frontend consumes.

**Tech Stack:** Python 3.11+, FastAPI, Starlette, `sse-starlette`, `uvicorn`, `python-multipart`, pytest. Engine is plain stdlib + ffmpeg.

## Global Constraints

- **Python** `>=3.11` (repo `requires-python`). Dev venv at `./.venv`; run tests with `./.venv/bin/pytest`.
- **Ruff** line-length `100`, target `py311`. Run `./.venv/bin/ruff check .` — must be clean.
- **TDD, red→green→refactor.** Write the failing test first; show it fail; minimal implementation; show it pass; commit.
- **Engine stays light + offline.** FastAPI and friends go in a `server` optional-dependency extra and are imported only inside `variant_maker/server/` — never from core engine modules (`pipeline`, `quality`, etc.). The two engine edits in Task 3 add only an optional stdlib-typed callback param; they import nothing new.
- **Status mapping (locked):** engine `status` `"ok"` → delivered (Gallery). `"best_effort"` and `"corrupt"` → Diagnostics, and count as a shortfall. `delivered = count(status=="ok")`; `shortfall = requested - delivered`.
- **Defaults (locked):** Stage-1 LocalRunner uses `quality_mode="fast"` (Tier-1 CPU, no GPU), `preset="medium"`, `platform="tiktok"` (vertical 1080×1920), `max_regen=3` (auto-retry cap), `jobs=1` (sequential → clean ordered events). Output format default = vertical; `platform="none"` (keep-source) is the advanced override.
- **Count is per-video, one shared config per run.** A job of M videos with count N targets N variants per video.
- **No DB.** Filesystem workspace only. In-memory job registry (lost on restart — acceptable for Stage 1).

---

## File Structure

**Engine edits (core — minimal, no new imports):**
- `variant_maker/quality.py` — `regen_until_pass` gains an `on_regen` callback.
- `variant_maker/pipeline.py` — `run` gains an `on_event` callback, threaded into the per-variant loop.

**New subpackage `variant_maker/server/`:**
- `events.py` — `VariantEvent` dataclass + `event_to_dict`. The progress contract.
- `workspace.py` — `Workspace`: filesystem layout for uploads / outputs / manifests.
- `runner.py` — `Runner` protocol, `VariantResult`/`SourceResult`, `LocalRunner` (wraps `pipeline.run`).
- `jobs.py` — `JobSource`, `Job`, `JobStore` (background execution + per-job event log + gallery/diagnostics views).
- `models.py` — Pydantic request/response models (the HTTP contract).
- `app.py` — `create_app(store)` factory; all routes.
- `cli.py` — `variant-server` entrypoint (launches uvicorn).
- `__init__.py` — package marker.

**Tests (`tests/server/`):**
- `tests/server/__init__.py`
- `tests/server/fakes.py` — `FakeRunner` (deterministic, no ffmpeg).
- `tests/server/test_workspace.py`, `test_runner.py`, `test_jobs.py`, `test_app.py`
- `tests/test_quality.py` (extend) — `on_regen` fires.
- `tests/test_pipeline_events.py` (new) — `on_event` order, via monkeypatched render (unit) + one integration test.

**Config:**
- `pyproject.toml` — add `server` extra + `variant-server` script.

---

## Task 1: Project setup — `server` extra + package skeleton + health route

**Files:**
- Modify: `pyproject.toml`
- Create: `variant_maker/server/__init__.py`, `variant_maker/server/app.py`
- Create: `tests/server/__init__.py`, `tests/server/test_app.py`

**Interfaces:**
- Produces: `variant_maker.server.app.create_app() -> fastapi.FastAPI`, exposing `GET /api/health` → `{"status": "ok"}`.

- [ ] **Step 1: Add the `server` extra and script to `pyproject.toml`**

In `[project.optional-dependencies]` add:

```toml
server = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "sse-starlette>=2.1",
    "python-multipart>=0.0.9",
    "httpx>=0.27",
]
```

In `[project.scripts]` add:

```toml
variant-server = "variant_maker.server.cli:main"
```

- [ ] **Step 2: Install the extra and verify it imports on this interpreter**

Run: `./.venv/bin/pip install -e ".[dev,server]"`
Then: `./.venv/bin/python -c "import fastapi, sse_starlette, multipart; print('ok')"`
Expected: prints `ok`. (If a dependency lacks a wheel for the venv's Python, recreate `./.venv` on Python 3.12 and re-run — note it and continue.)

- [ ] **Step 3: Write the failing health-route test**

Create `tests/server/__init__.py` (empty) and `tests/server/test_app.py`:

```python
from fastapi.testclient import TestClient

from variant_maker.server.app import create_app


def test_health_ok():
    client = TestClient(create_app())
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 4: Run it; verify it fails**

Run: `./.venv/bin/pytest tests/server/test_app.py -q`
Expected: FAIL — `ModuleNotFoundError: variant_maker.server.app` (or `create_app` undefined).

- [ ] **Step 5: Create the package + minimal app**

Create `variant_maker/server/__init__.py` (empty). Create `variant_maker/server/app.py`:

```python
"""FastAPI control-plane app. Imported only with the `server` extra installed."""
from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="variant-maker control plane")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    return app
```

- [ ] **Step 6: Run it; verify it passes**

Run: `./.venv/bin/pytest tests/server/test_app.py -q`
Expected: PASS (1 passed).

- [ ] **Step 7: Lint + commit**

Run: `./.venv/bin/ruff check .` (expect clean).

```bash
git add pyproject.toml variant_maker/server/__init__.py variant_maker/server/app.py tests/server/__init__.py tests/server/test_app.py
git commit -m "feat(server): scaffold control-plane FastAPI app + server extra"
```

---

## Task 2: Event schema (`events.py`)

**Files:**
- Create: `variant_maker/server/events.py`
- Create: `tests/server/test_runner.py` (event tests live here; runner is added in Task 5)

**Interfaces:**
- Produces:
  - `VariantEvent` dataclass: `source_id: str`, `index: int`, `state: str`, `attempt: int = 0`, `max_attempts: int = 0`, `status: str | None = None`, `quality: dict | None = None`, `filename: str | None = None`.
  - `state` is one of `"rendering" | "checking" | "rerolling" | "done"`.
  - `event_to_dict(e: VariantEvent) -> dict` — JSON-safe dict for SSE payloads.

- [ ] **Step 1: Write the failing test**

In `tests/server/test_runner.py`:

```python
from variant_maker.server.events import VariantEvent, event_to_dict


def test_variant_event_to_dict_roundtrips_fields():
    e = VariantEvent(
        source_id="s1", index=3, state="done",
        attempt=2, max_attempts=3, status="ok",
        quality={"vmaf": 91.0}, filename="clip_v03_abcd1234.mp4",
    )
    d = event_to_dict(e)
    assert d == {
        "source_id": "s1", "index": 3, "state": "done",
        "attempt": 2, "max_attempts": 3, "status": "ok",
        "quality": {"vmaf": 91.0}, "filename": "clip_v03_abcd1234.mp4",
    }


def test_variant_event_defaults():
    e = VariantEvent(source_id="s1", index=1, state="rendering")
    d = event_to_dict(e)
    assert d["attempt"] == 0 and d["status"] is None and d["quality"] is None
```

- [ ] **Step 2: Run it; verify it fails**

Run: `./.venv/bin/pytest tests/server/test_runner.py -q`
Expected: FAIL — `ModuleNotFoundError: variant_maker.server.events`.

- [ ] **Step 3: Implement `events.py`**

```python
"""The progress contract: one event per variant state transition."""
from __future__ import annotations

from dataclasses import asdict, dataclass

# Valid VariantEvent.state values, in lifecycle order.
STATES = ("rendering", "checking", "rerolling", "done")


@dataclass
class VariantEvent:
    source_id: str
    index: int
    state: str
    attempt: int = 0          # rerolling: which retry (1..max_attempts)
    max_attempts: int = 0
    status: str | None = None     # done: "ok" | "best_effort" | "corrupt"
    quality: dict | None = None   # done: vmaf/histogram_ok/spatial_ok/regen_count
    filename: str | None = None   # done: rendered file name


def event_to_dict(e: VariantEvent) -> dict:
    """JSON-safe dict for SSE/data payloads."""
    return asdict(e)
```

- [ ] **Step 4: Run it; verify it passes**

Run: `./.venv/bin/pytest tests/server/test_runner.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add variant_maker/server/events.py tests/server/test_runner.py
git commit -m "feat(server): VariantEvent progress schema"
```

---

## Task 3: Engine progress seam (`quality.py` + `pipeline.py`)

The engine must announce per-variant progress so the backend can stream it. This is the one core-engine change. It adds only optional callbacks (default `None` → existing behavior unchanged).

**Files:**
- Modify: `variant_maker/quality.py` (`regen_until_pass`)
- Modify: `variant_maker/pipeline.py` (`run`, `_render_one`)
- Modify: `tests/test_quality.py` (add `on_regen` test)
- Create: `tests/test_pipeline_events.py`

**Interfaces:**
- Produces:
  - `quality.regen_until_pass(attempt, *, max_regen=3, strength=1.0, falloff=0.6, on_regen=None)`. `on_regen(regen: int, max_regen: int)` is called once before each retry attempt (`regen` = 1..max_regen). Default `None` = no-op.
  - `pipeline.run(config, *, on_event=None)`. `on_event(state: str, **kw)` is called with:
    - `state="rendering"`, `index: int`, `attempt: int` (0 = first try)
    - `state="checking"`, `index: int`
    - `state="rerolling"`, `index: int`, `attempt: int`, `max_attempts: int`
    - `state="done"`, `index: int`, `status: str`, `quality: dict`, `filename: str`
    Default `None` = no-op (current behavior).

- [ ] **Step 1: Write the failing `on_regen` test**

Append to `tests/test_quality.py`:

```python
def test_regen_until_pass_calls_on_regen_each_retry():
    from variant_maker import quality

    calls = []
    results = [
        {"passed": False}, {"passed": False}, {"passed": True},
    ]

    def attempt(strength):
        return results[len(calls)] if False else results.pop(0)

    out = quality.regen_until_pass(
        attempt, max_regen=3, strength=1.0,
        on_regen=lambda regen, mx: calls.append((regen, mx)),
    )
    assert out["passed"] is True
    assert out["regen_count"] == 2
    assert calls == [(1, 3), (2, 3)]


def test_regen_until_pass_on_regen_optional():
    from variant_maker import quality
    out = quality.regen_until_pass(lambda s: {"passed": True}, max_regen=3)
    assert out["regen_count"] == 0  # no on_regen, no error
```

- [ ] **Step 2: Run it; verify it fails**

Run: `./.venv/bin/pytest tests/test_quality.py -k on_regen -q`
Expected: FAIL — `regen_until_pass() got an unexpected keyword argument 'on_regen'`.

- [ ] **Step 3: Implement `on_regen` in `regen_until_pass`**

Replace the body of `regen_until_pass` in `variant_maker/quality.py`:

```python
def regen_until_pass(attempt, *, max_regen: int = 3, strength: float = 1.0,
                     falloff: float = 0.6, on_regen=None) -> dict:
    """Reject -> reduce strength -> regenerate, bounded by max_regen.

    `attempt(strength) -> dict` samples + renders + guards one variant and returns its guard
    result (must include 'passed'). On failure, strength is scaled by `falloff` and retried.
    `on_regen(regen, max_regen)` (optional) fires once before each retry. Returns the first
    passing result, else the best-effort last attempt; tags 'regen_count'.
    """
    result = attempt(strength)
    regen = 0
    while not result["passed"] and regen < max_regen:
        regen += 1
        if on_regen is not None:
            on_regen(regen, max_regen)
        strength *= falloff
        result = attempt(strength)
    return {**result, "regen_count": regen}
```

- [ ] **Step 4: Run it; verify it passes**

Run: `./.venv/bin/pytest tests/test_quality.py -k on_regen -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Write the failing pipeline-events test (unit, no ffmpeg)**

Create `tests/test_pipeline_events.py`:

```python
"""pipeline.run emits ordered progress events. ffmpeg/probe are monkeypatched so this
runs as a fast unit test."""
from __future__ import annotations

from variant_maker import pipeline
from variant_maker.manifest import VariantRecord


def test_run_emits_events_in_order(monkeypatch, tmp_path):
    # --- stub out everything heavy so run() is pure orchestration ---
    class FakeSrc:
        path = "src.mp4"
        sha256 = "deadbeef"
        duration_s = 1.0
        def to_dict(self):
            return {"path": self.path, "sha256": self.sha256}

    monkeypatch.setattr(pipeline, "probe", lambda p: FakeSrc())
    monkeypatch.setattr(pipeline, "_ffmpeg_version", lambda: "test")
    monkeypatch.setattr(pipeline, "sample", lambda preset, seed, strength=1.0: {
        "video": {"rotate_deg": 0.0}, "audio": {},
    })

    # render_variant just "creates" the output and returns a fake cmd.
    def fake_render(src, params, platform, path, dry_run=False):
        open(path, "w").close()
        return (path, "ffmpeg -y fake")
    monkeypatch.setattr(pipeline, "render_variant", fake_render)

    # quality_render + passes_guard: first variant passes immediately, second needs 1 reroll.
    monkeypatch.setattr(pipeline.quality, "quality_render", lambda src, params, qr: open(qr, "w").close())
    calls = {"n": 0}
    def fake_guard(src_path, variant_path, qr, floor=90.0):
        calls["n"] += 1
        # variant 1 (calls 1) passes; variant 2 (calls 2,3) fails then passes
        passed = calls["n"] != 2
        return {"vmaf": 95.0 if passed else 50.0, "histogram_ok": True, "passed": passed}
    monkeypatch.setattr(pipeline.quality, "passes_guard", fake_guard)

    events = []
    cfg = {
        "input": "src.mp4", "count": 2, "preset": "medium", "platform": "none",
        "out": str(tmp_path), "quality_mode": "fast", "jobs": 1, "max_regen": 3,
    }
    pipeline.run(cfg, on_event=lambda state, **kw: events.append((state, kw.get("index"))))

    states = [e[0] for e in events]
    # variant 1: rendering, checking, done
    assert states[:3] == ["rendering", "checking", "done"]
    # somewhere a rerolling event for variant 2
    assert "rerolling" in states
    # exactly two 'done' events, one per variant
    assert states.count("done") == 2
    # done events carry status + filename
    done = [e for e in events if e[0] == "done"]
    assert len(done) == 2
```

- [ ] **Step 6: Run it; verify it fails**

Run: `./.venv/bin/pytest tests/test_pipeline_events.py -q`
Expected: FAIL — `run() got an unexpected keyword argument 'on_event'`.

- [ ] **Step 7: Thread `on_event` through `pipeline.run`**

In `variant_maker/pipeline.py`, change the signature:

```python
def run(config: dict, *, on_event=None) -> Manifest:
```

Add a no-op normalizer just after the signature (before reading config):

```python
    emit = on_event if on_event is not None else (lambda *a, **k: None)
```

Replace the `_render_one` function's `attempt` closure and `regen_until_pass` call with the event-emitting version:

```python
    def _render_one(i: int) -> VariantRecord:
        vseed, fname, path = _prep(i)

        def attempt(strength: float) -> dict:
            emit("rendering", index=i)
            params = sample(preset, vseed, strength=strength)
            if rotate_off:
                params["video"]["rotate_deg"] = 0.0
            if hq:
                _, cmd, nops = neural.upscale_clip(src, params, path, platform=platform)
            else:
                _, cmd = render_variant(src, params, platform, path)
                nops = []
            qr = path + ".qr.mp4"
            quality.quality_render(src, params, qr)
            emit("checking", index=i)
            g = quality.passes_guard(src.path, path, qr, floor=floor)
            for tmp in (qr, qr + ".vmaf.json"):
                if os.path.exists(tmp):
                    os.remove(tmp)
            return {**g, "params": params, "cmd": cmd, "neural_ops": nops}

        r = quality.regen_until_pass(
            attempt, max_regen=max_regen, strength=1.0,
            on_regen=lambda regen, mx: emit("rerolling", index=i, attempt=regen, max_attempts=mx),
        )
        info = probe(path)

        spatial_vmaf = None
        spatial_ok = None
        if r["neural_ops"] and "spatial_vmaf" in r["neural_ops"][0]:
            spatial_vmaf = r["neural_ops"][0]["spatial_vmaf"]
            spatial_ok = spatial_vmaf >= corruption_floor

        if spatial_ok is False:
            status = "corrupt"
        elif r["passed"]:
            status = "ok"
        else:
            status = "best_effort"

        quality_info = {
            "vmaf": round(r["vmaf"], 2), "histogram_ok": r["histogram_ok"],
            "regen_count": r["regen_count"], "passed": r["passed"],
            "spatial_vmaf": spatial_vmaf, "spatial_ok": spatial_ok,
        }
        emit("done", index=i, status=status, quality=quality_info, filename=fname)

        return VariantRecord(
            index=i, filename=fname, seed=vseed, params=r["params"], ffmpeg_cmd=r["cmd"],
            tier=2 if r["neural_ops"] else 1, neural_ops=r["neural_ops"],
            quality=quality_info,
            output_sha256=info.sha256, duration_s=info.duration_s,
            status=status,
        )
```

(Leave the `dry_run` branch, the `jobs > 1` ThreadPoolExecutor path, and `manifest.write` untouched. Events are still emitted under `jobs>1`, just interleaved — Stage 1 uses `jobs=1`.)

- [ ] **Step 8: Run the new + existing pipeline/quality tests; verify green**

Run: `./.venv/bin/pytest tests/test_pipeline_events.py tests/test_quality.py tests/test_pipeline.py -q`
Expected: PASS (new event test + all pre-existing pipeline/quality tests still pass — the callbacks are additive).

- [ ] **Step 9: Lint + commit**

Run: `./.venv/bin/ruff check .` (clean).

```bash
git add variant_maker/quality.py variant_maker/pipeline.py tests/test_quality.py tests/test_pipeline_events.py
git commit -m "feat(engine): optional on_event/on_regen progress callbacks"
```

---

## Task 4: Workspace (`workspace.py`)

**Files:**
- Create: `variant_maker/server/workspace.py`
- Create: `tests/server/test_workspace.py`

**Interfaces:**
- Produces `Workspace`:
  - `Workspace(root: str)`
  - `save_upload(job_id: str, source_id: str, filename: str, data: bytes) -> str` — writes the source video, returns its absolute path.
  - `source_in_path(job_id, source_id, filename) -> str`
  - `source_out_dir(job_id, source_id) -> str` — created on demand; where `pipeline.run` writes variants + `manifest.json`.
  - `variant_path(job_id, source_id, filename) -> str`

Layout: `<root>/jobs/<job_id>/<source_id>/in/<filename>` and `.../<source_id>/out/<variant files + manifest.json>`.

- [ ] **Step 1: Write the failing test**

```python
# tests/server/test_workspace.py
from variant_maker.server.workspace import Workspace


def test_save_upload_writes_file_and_returns_path(tmp_path):
    ws = Workspace(str(tmp_path))
    p = ws.save_upload("job1", "srcA", "clip.mp4", b"\x00\x01data")
    assert p.endswith("/jobs/job1/srcA/in/clip.mp4")
    with open(p, "rb") as f:
        assert f.read() == b"\x00\x01data"


def test_out_dir_created_and_under_source(tmp_path):
    ws = Workspace(str(tmp_path))
    out = ws.source_out_dir("job1", "srcA")
    assert out.endswith("/jobs/job1/srcA/out")
    import os
    assert os.path.isdir(out)


def test_variant_path_composes(tmp_path):
    ws = Workspace(str(tmp_path))
    vp = ws.variant_path("job1", "srcA", "clip_v01_abcd.mp4")
    assert vp.endswith("/jobs/job1/srcA/out/clip_v01_abcd.mp4")
```

- [ ] **Step 2: Run it; verify it fails**

Run: `./.venv/bin/pytest tests/server/test_workspace.py -q`
Expected: FAIL — `ModuleNotFoundError: variant_maker.server.workspace`.

- [ ] **Step 3: Implement `workspace.py`**

```python
"""Filesystem layout for the local control plane. One directory tree per job."""
from __future__ import annotations

import os


class Workspace:
    def __init__(self, root: str) -> None:
        self.root = os.path.abspath(root)

    def _source_dir(self, job_id: str, source_id: str) -> str:
        return os.path.join(self.root, "jobs", job_id, source_id)

    def source_in_path(self, job_id: str, source_id: str, filename: str) -> str:
        return os.path.join(self._source_dir(job_id, source_id), "in", filename)

    def source_out_dir(self, job_id: str, source_id: str) -> str:
        out = os.path.join(self._source_dir(job_id, source_id), "out")
        os.makedirs(out, exist_ok=True)
        return out

    def variant_path(self, job_id: str, source_id: str, filename: str) -> str:
        return os.path.join(self.source_out_dir(job_id, source_id), filename)

    def save_upload(self, job_id: str, source_id: str, filename: str, data: bytes) -> str:
        path = self.source_in_path(job_id, source_id, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path
```

- [ ] **Step 4: Run it; verify it passes**

Run: `./.venv/bin/pytest tests/server/test_workspace.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add variant_maker/server/workspace.py tests/server/test_workspace.py
git commit -m "feat(server): filesystem Workspace layout"
```

---

## Task 5: Runner protocol + LocalRunner + FakeRunner

**Files:**
- Create: `variant_maker/server/runner.py`
- Create: `tests/server/fakes.py`
- Modify: `tests/server/test_runner.py` (add runner tests alongside the event tests)

**Interfaces:**
- Produces:
  - `VariantResult` dataclass: `index: int`, `filename: str`, `status: str`, `quality: dict`, `path: str`.
  - `SourceResult` dataclass: `variants: list[VariantResult]`, `manifest_path: str`.
  - `Runner` protocol: `run(self, source_path: str, *, count: int, out_dir: str, source_id: str, on_event: Callable[[VariantEvent], None]) -> SourceResult`.
  - `LocalRunner` (implements `Runner`) — wraps `pipeline.run`, fast/Tier-1, defaults from Global Constraints. Translates engine `on_event(state, **kw)` → `VariantEvent(source_id=..., ...)` and forwards.
  - `tests/server/fakes.py`: `FakeRunner(plan: dict[int, str])` — emits the full event lifecycle and returns a `SourceResult` whose variant statuses come from `plan` (index → status), writing tiny placeholder files. No ffmpeg.

- [ ] **Step 1: Write failing tests (append to `tests/server/test_runner.py`)**

```python
from variant_maker.server.events import VariantEvent
from variant_maker.server.runner import LocalRunner, SourceResult, VariantResult


def test_localrunner_translates_engine_events_and_maps_results(monkeypatch, tmp_path):
    from variant_maker.server import runner as runner_mod

    # Fake pipeline.run: emit engine events for 2 variants, write files, return a manifest.
    class FakeManifest:
        def __init__(self, variants):
            self.variants = variants

    class FakeRecord:
        def __init__(self, index, filename, status, quality):
            self.index, self.filename, self.status, self.quality = index, filename, status, quality

    def fake_run(config, *, on_event=None):
        out = config["out"]
        recs = []
        for i, status in [(1, "ok"), (2, "best_effort")]:
            fname = f"clip_v0{i}_x.mp4"
            on_event("rendering", index=i)
            on_event("checking", index=i)
            on_event("done", index=i, status=status,
                     quality={"vmaf": 95.0 if status == "ok" else 50.0}, filename=fname)
            open(f"{out}/{fname}", "w").close()
            recs.append(FakeRecord(i, fname, status, {"vmaf": 95.0}))
        open(f"{out}/manifest.json", "w").close()
        return FakeManifest(recs)

    monkeypatch.setattr(runner_mod.pipeline, "run", fake_run)

    events: list[VariantEvent] = []
    out_dir = str(tmp_path)
    result = LocalRunner().run(
        "src.mp4", count=2, out_dir=out_dir, source_id="srcA",
        on_event=events.append,
    )

    assert isinstance(result, SourceResult)
    assert [v.status for v in result.variants] == ["ok", "best_effort"]
    assert all(isinstance(v, VariantResult) for v in result.variants)
    # every forwarded event is tagged with the source_id
    assert events and all(e.source_id == "srcA" for e in events)
    # lifecycle present, done events carry status
    states = [e.state for e in events]
    assert "rendering" in states and "done" in states
    assert {e.status for e in events if e.state == "done"} == {"ok", "best_effort"}


def test_localrunner_sets_fast_tier1_defaults(monkeypatch, tmp_path):
    from variant_maker.server import runner as runner_mod
    captured = {}

    def fake_run(config, *, on_event=None):
        captured.update(config)
        open(f"{config['out']}/manifest.json", "w").close()
        class M: variants = []
        return M()

    monkeypatch.setattr(runner_mod.pipeline, "run", fake_run)
    LocalRunner().run("src.mp4", count=5, out_dir=str(tmp_path), source_id="s", on_event=lambda e: None)
    assert captured["quality_mode"] == "fast"
    assert captured["preset"] == "medium"
    assert captured["platform"] == "tiktok"
    assert captured["max_regen"] == 3
    assert captured["jobs"] == 1
    assert captured["count"] == 5
```

- [ ] **Step 2: Run; verify it fails**

Run: `./.venv/bin/pytest tests/server/test_runner.py -q`
Expected: FAIL — `ModuleNotFoundError: variant_maker.server.runner`.

- [ ] **Step 3: Implement `runner.py`**

```python
"""Runner seam: 'render one source into N variants', abstracted so a GPU runner drops in.

LocalRunner wraps the in-process engine (pipeline.run, Tier-1 CPU). A future
RunPodServerlessRunner implements the same protocol against a serverless GPU endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from .. import pipeline
from .events import VariantEvent

# Stage-1 LocalRunner defaults (see plan Global Constraints).
DEFAULT_PRESET = "medium"
DEFAULT_PLATFORM = "tiktok"   # vertical 1080x1920
DEFAULT_QUALITY_MODE = "fast"  # Tier-1 CPU, no GPU
MAX_REGEN = 3


@dataclass
class VariantResult:
    index: int
    filename: str
    status: str
    quality: dict
    path: str


@dataclass
class SourceResult:
    variants: list[VariantResult]
    manifest_path: str


class Runner(Protocol):
    def run(self, source_path: str, *, count: int, out_dir: str, source_id: str,
            on_event: Callable[[VariantEvent], None]) -> SourceResult:
        ...


class LocalRunner:
    """In-process engine runner. Translates engine callbacks into VariantEvents."""

    def run(self, source_path: str, *, count: int, out_dir: str, source_id: str,
            on_event: Callable[[VariantEvent], None]) -> SourceResult:
        def engine_event(state: str, **kw) -> None:
            on_event(VariantEvent(
                source_id=source_id,
                index=kw["index"],
                state=state,
                attempt=kw.get("attempt", 0),
                max_attempts=kw.get("max_attempts", 0),
                status=kw.get("status"),
                quality=kw.get("quality"),
                filename=kw.get("filename"),
            ))

        config = {
            "input": source_path,
            "out": out_dir,
            "count": count,
            "preset": DEFAULT_PRESET,
            "platform": DEFAULT_PLATFORM,
            "quality_mode": DEFAULT_QUALITY_MODE,
            "max_regen": MAX_REGEN,
            "jobs": 1,
        }
        manifest = pipeline.run(config, on_event=engine_event)
        import os
        variants = [
            VariantResult(
                index=v.index, filename=v.filename, status=v.status,
                quality=v.quality, path=os.path.join(out_dir, v.filename),
            )
            for v in manifest.variants
        ]
        return SourceResult(variants=variants, manifest_path=os.path.join(out_dir, "manifest.json"))
```

- [ ] **Step 4: Run; verify it passes**

Run: `./.venv/bin/pytest tests/server/test_runner.py -q`
Expected: PASS (event tests from Task 2 + the two runner tests).

- [ ] **Step 5: Implement `FakeRunner` for downstream tests**

Create `tests/server/fakes.py`:

```python
"""A deterministic Runner that needs no ffmpeg — for JobStore / app tests."""
from __future__ import annotations

import os
from typing import Callable

from variant_maker.server.events import VariantEvent
from variant_maker.server.runner import SourceResult, VariantResult


class FakeRunner:
    """plan: {variant_index: status}. Emits the full lifecycle and writes placeholder files."""

    def __init__(self, plan: dict[int, str] | None = None) -> None:
        # default: variant 1 ok, variant 2 best_effort, rest ok
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
```

- [ ] **Step 6: Commit**

```bash
git add variant_maker/server/runner.py tests/server/fakes.py tests/server/test_runner.py
git commit -m "feat(server): Runner protocol + LocalRunner + FakeRunner"
```

---

## Task 6: Job model + JobStore (`jobs.py`)

**Files:**
- Create: `variant_maker/server/jobs.py`
- Create: `tests/server/test_jobs.py`

**Interfaces:**
- Produces:
  - `VariantInfo` dataclass: `source_id: str`, `index: int`, `filename: str`, `status: str`, `quality: dict`.
  - `JobSource` dataclass: `source_id: str`, `filename: str`, `requested: int`, `variants: list[VariantInfo]` (default `[]`); property `delivered -> int` (count `status=="ok"`); property `shortfall -> int` (`requested - delivered`).
  - `Job` dataclass: `job_id: str`, `count: int`, `created_utc: str`, `sources: list[JobSource]`, `state: str` (`"running" | "done"`), `events: list[VariantEvent]` (default `[]`).
  - `JobStore(workspace, runner)`:
    - `create_job(uploads: list[tuple[str, bytes]], count: int) -> Job` — `uploads` = `(filename, data)`. Persists uploads, builds `Job` (state `"running"`), starts a background thread that runs each source through the runner, appends events to `job.events`, fills `source.variants`, sets `job.state="done"` at the end. Returns immediately.
    - `get(job_id) -> Job | None`
    - `list() -> list[Job]`
    - `wait(job_id, timeout=...)` — test helper: block until `state=="done"`.
    - `gallery() -> list[JobSource]` — all sources across jobs, each carrying only `status=="ok"` variants (for the Gallery view; delivered/shortfall still computed from the full set — see note).
    - `diagnostics() -> list[VariantInfo]` — all variants across jobs with `status in ("best_effort","corrupt")`.

> **Delivered/shortfall note:** `delivered` and `shortfall` are computed from the *full* variant set (ok + non-ok). `gallery()` returns sources with their full `variants` list intact but the route (Task 9) serializes only the `ok` ones into cards while still surfacing `delivered`/`shortfall`/`requested`. Keep the full list on `JobSource` so the math stays correct; filter at the serialization boundary, not in the model.

- [ ] **Step 1: Write failing tests**

```python
# tests/server/test_jobs.py
from variant_maker.server.jobs import JobStore
from variant_maker.server.workspace import Workspace
from tests.server.fakes import FakeRunner


def _store(tmp_path, plan=None):
    return JobStore(Workspace(str(tmp_path)), FakeRunner(plan or {}))


def test_create_job_runs_in_background_and_completes(tmp_path):
    store = _store(tmp_path)
    job = store.create_job([("a.mp4", b"x"), ("b.mp4", b"y")], count=3)
    assert job.state in ("running", "done")
    store.wait(job.job_id, timeout=5)
    done = store.get(job.job_id)
    assert done.state == "done"
    assert len(done.sources) == 2
    for s in done.sources:
        assert len(s.variants) == 3
        assert s.requested == 3


def test_delivered_and_shortfall_count_only_ok(tmp_path):
    # variant 2 is best_effort -> delivered 2 of 3, shortfall 1
    store = _store(tmp_path, plan={2: "best_effort"})
    job = store.create_job([("a.mp4", b"x")], count=3)
    store.wait(job.job_id, timeout=5)
    src = store.get(job.job_id).sources[0]
    assert src.delivered == 2
    assert src.shortfall == 1


def test_events_recorded_per_job(tmp_path):
    store = _store(tmp_path)
    job = store.create_job([("a.mp4", b"x")], count=2)
    store.wait(job.job_id, timeout=5)
    states = [e.state for e in store.get(job.job_id).events]
    assert states.count("done") == 2
    assert "rendering" in states


def test_gallery_and_diagnostics_split_by_status(tmp_path):
    store = _store(tmp_path, plan={2: "best_effort"})
    job = store.create_job([("a.mp4", b"x")], count=3)
    store.wait(job.job_id, timeout=5)

    gallery = store.gallery()
    assert len(gallery) == 1
    ok_in_gallery = [v for v in gallery[0].variants if v.status == "ok"]
    assert len(ok_in_gallery) == 2

    diag = store.diagnostics()
    assert len(diag) == 1
    assert diag[0].status == "best_effort"
```

- [ ] **Step 2: Run; verify it fails**

Run: `./.venv/bin/pytest tests/server/test_jobs.py -q`
Expected: FAIL — `ModuleNotFoundError: variant_maker.server.jobs`.

- [ ] **Step 3: Implement `jobs.py`**

```python
"""In-memory job registry + background execution. No DB (Stage 1)."""
from __future__ import annotations

import datetime as _dt
import threading
import uuid
from dataclasses import dataclass, field

from .events import VariantEvent
from .runner import Runner
from .workspace import Workspace


@dataclass
class VariantInfo:
    source_id: str
    index: int
    filename: str
    status: str
    quality: dict


@dataclass
class JobSource:
    source_id: str
    filename: str
    requested: int
    variants: list[VariantInfo] = field(default_factory=list)

    @property
    def delivered(self) -> int:
        return sum(1 for v in self.variants if v.status == "ok")

    @property
    def shortfall(self) -> int:
        return max(0, self.requested - self.delivered)


@dataclass
class Job:
    job_id: str
    count: int
    created_utc: str
    sources: list[JobSource] = field(default_factory=list)
    state: str = "running"
    events: list[VariantEvent] = field(default_factory=list)


def _now() -> str:
    return (_dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)
            .isoformat().replace("+00:00", "Z"))


class JobStore:
    def __init__(self, workspace: Workspace, runner: Runner) -> None:
        self._ws = workspace
        self._runner = runner
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._done: dict[str, threading.Event] = {}

    def create_job(self, uploads: list[tuple[str, bytes]], count: int) -> Job:
        job_id = uuid.uuid4().hex[:12]
        sources = []
        for filename, data in uploads:
            source_id = uuid.uuid4().hex[:12]
            self._ws.save_upload(job_id, source_id, filename, data)
            sources.append(JobSource(source_id=source_id, filename=filename, requested=count))
        job = Job(job_id=job_id, count=count, created_utc=_now(), sources=sources)
        with self._lock:
            self._jobs[job_id] = job
            self._done[job_id] = threading.Event()
        threading.Thread(target=self._run_job, args=(job,), daemon=True).start()
        return job

    def _run_job(self, job: Job) -> None:
        try:
            for source in job.sources:
                in_path = self._ws.source_in_path(job.job_id, source.source_id, source.filename)
                out_dir = self._ws.source_out_dir(job.job_id, source.source_id)

                def on_event(e: VariantEvent) -> None:
                    job.events.append(e)

                result = self._runner.run(
                    in_path, count=job.count, out_dir=out_dir,
                    source_id=source.source_id, on_event=on_event,
                )
                source.variants = [
                    VariantInfo(source_id=source.source_id, index=v.index, filename=v.filename,
                                status=v.status, quality=v.quality)
                    for v in result.variants
                ]
        finally:
            job.state = "done"
            self._done[job.job_id].set()

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        return list(self._jobs.values())

    def wait(self, job_id: str, timeout: float = 30.0) -> bool:
        ev = self._done.get(job_id)
        return ev.wait(timeout) if ev else False

    def gallery(self) -> list[JobSource]:
        with self._lock:
            return [s for job in self._jobs.values() for s in job.sources]

    def diagnostics(self) -> list[VariantInfo]:
        out = []
        with self._lock:
            for job in self._jobs.values():
                for s in job.sources:
                    out.extend(v for v in s.variants if v.status in ("best_effort", "corrupt"))
        return out
```

- [ ] **Step 4: Run; verify it passes**

Run: `./.venv/bin/pytest tests/server/test_jobs.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add variant_maker/server/jobs.py tests/server/test_jobs.py
git commit -m "feat(server): JobStore with background execution + event log"
```

---

## Task 7: API models (`models.py`)

**Files:**
- Create: `variant_maker/server/models.py`
- Test: covered via route tests in Tasks 8–10 (Pydantic models need no standalone test; their behavior is exercised by the endpoints).

**Interfaces:**
- Produces Pydantic models used by routes:
  - `VariantOut`: `index: int`, `filename: str`, `status: str`, `quality: dict`, `file_url: str`.
  - `SourceOut`: `source_id: str`, `filename: str`, `requested: int`, `delivered: int`, `shortfall: int`, `variants: list[VariantOut]`.
  - `JobSummary`: `job_id: str`, `count: int`, `created_utc: str`, `state: str`, `source_count: int`.
  - `JobDetail`: `job_id`, `count`, `created_utc`, `state`, `sources: list[SourceOut]`.
  - `CreateJobResponse`: `job_id: str`, `sources: list[SourceOut]`.
  - `DiagnosticsItem`: `source_id: str`, `index: int`, `filename: str`, `status: str`, `quality: dict`.

- [ ] **Step 1: Implement `models.py`** (no separate failing test; exercised by Task 8)

```python
"""Pydantic response models — the HTTP contract the frontend consumes."""
from __future__ import annotations

from pydantic import BaseModel


class VariantOut(BaseModel):
    index: int
    filename: str
    status: str
    quality: dict
    file_url: str


class SourceOut(BaseModel):
    source_id: str
    filename: str
    requested: int
    delivered: int
    shortfall: int
    variants: list[VariantOut] = []


class JobSummary(BaseModel):
    job_id: str
    count: int
    created_utc: str
    state: str
    source_count: int


class JobDetail(BaseModel):
    job_id: str
    count: int
    created_utc: str
    state: str
    sources: list[SourceOut] = []


class CreateJobResponse(BaseModel):
    job_id: str
    sources: list[SourceOut] = []


class DiagnosticsItem(BaseModel):
    source_id: str
    index: int
    filename: str
    status: str
    quality: dict
```

- [ ] **Step 2: Verify it imports**

Run: `./.venv/bin/python -c "from variant_maker.server import models; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add variant_maker/server/models.py
git commit -m "feat(server): Pydantic response models"
```

---

## Task 8: Routes — job create / list / get + SSE progress

**Files:**
- Modify: `variant_maker/server/app.py`
- Modify: `tests/server/test_app.py`

**Interfaces:**
- `create_app(store: JobStore | None = None) -> FastAPI` — when `store is None`, builds a default `JobStore(Workspace("./.vmdata"), LocalRunner())`. Tests pass a `JobStore(Workspace(tmp), FakeRunner())`.
- Routes:
  - `POST /api/jobs` (multipart: `files` = one or more uploads, `count: int` form field) → `CreateJobResponse` (201). Starts the job.
  - `GET /api/jobs` → `list[JobSummary]`.
  - `GET /api/jobs/{job_id}` → `JobDetail` (404 if unknown).
  - `GET /api/jobs/{job_id}/events` → SSE stream of `event_to_dict(VariantEvent)` payloads; emits a terminal `{"state": "job-done"}` event when the job finishes.
- Helper (module-level in `app.py`): `_source_out(s: JobSource, ok_only: bool) -> SourceOut` — builds a `SourceOut`, filtering variants to `status=="ok"` when `ok_only`, always setting `delivered`/`shortfall`/`requested` from the model.

- [ ] **Step 1: Write failing tests (append to `tests/server/test_app.py`)**

```python
import json
from variant_maker.server.app import create_app
from variant_maker.server.jobs import JobStore
from variant_maker.server.workspace import Workspace
from tests.server.fakes import FakeRunner


def _client(tmp_path, plan=None):
    store = JobStore(Workspace(str(tmp_path)), FakeRunner(plan or {}))
    return TestClient(create_app(store)), store


def test_create_job_returns_sources(tmp_path):
    client, store = _client(tmp_path)
    resp = client.post(
        "/api/jobs",
        files=[("files", ("a.mp4", b"x", "video/mp4")),
               ("files", ("b.mp4", b"y", "video/mp4"))],
        data={"count": "3"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["sources"]) == 2
    assert body["sources"][0]["requested"] == 3
    store.wait(body["job_id"], timeout=5)


def test_get_job_detail_shows_ok_variants_and_counts(tmp_path):
    client, store = _client(tmp_path, plan={2: "best_effort"})
    job_id = client.post("/api/jobs",
                         files=[("files", ("a.mp4", b"x", "video/mp4"))],
                         data={"count": "3"}).json()["job_id"]
    store.wait(job_id, timeout=5)
    detail = client.get(f"/api/jobs/{job_id}").json()
    src = detail["sources"][0]
    assert src["delivered"] == 2 and src["shortfall"] == 1
    assert [v["status"] for v in src["variants"]] == ["ok", "ok"]  # ok-only in cards


def test_get_unknown_job_404(tmp_path):
    client, _ = _client(tmp_path)
    assert client.get("/api/jobs/nope").status_code == 404


def test_sse_events_stream_until_job_done(tmp_path):
    client, store = _client(tmp_path)
    job_id = client.post("/api/jobs",
                         files=[("files", ("a.mp4", b"x", "video/mp4"))],
                         data={"count": "2"}).json()["job_id"]
    store.wait(job_id, timeout=5)
    # stream is replayable from the recorded event log after completion
    with client.stream("GET", f"/api/jobs/{job_id}/events") as r:
        payloads = []
        for line in r.iter_lines():
            if line.startswith("data:"):
                payloads.append(json.loads(line[len("data:"):].strip()))
                if payloads[-1].get("state") == "job-done":
                    break
    states = [p.get("state") for p in payloads]
    assert states.count("done") == 2
    assert states[-1] == "job-done"
```

- [ ] **Step 2: Run; verify it fails**

Run: `./.venv/bin/pytest tests/server/test_app.py -q`
Expected: FAIL — `create_app()` takes no `store` arg / routes missing.

- [ ] **Step 3: Rewrite `app.py` with the store + routes**

```python
"""FastAPI control-plane app."""
from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from .events import event_to_dict
from .jobs import JobSource, JobStore
from .models import (CreateJobResponse, JobDetail, JobSummary, SourceOut, VariantOut)
from .runner import LocalRunner
from .workspace import Workspace


def _source_out(s: JobSource, *, ok_only: bool) -> SourceOut:
    variants = [v for v in s.variants if (v.status == "ok" or not ok_only)]
    return SourceOut(
        source_id=s.source_id, filename=s.filename, requested=s.requested,
        delivered=s.delivered, shortfall=s.shortfall,
        variants=[
            VariantOut(index=v.index, filename=v.filename, status=v.status, quality=v.quality,
                       file_url=f"/api/variants/{s.source_id}/{v.filename}")
            for v in variants
        ],
    )


def create_app(store: JobStore | None = None) -> FastAPI:
    if store is None:
        store = JobStore(Workspace("./.vmdata"), LocalRunner())
    app = FastAPI(title="variant-maker control plane")
    app.state.store = store

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/api/jobs", status_code=201, response_model=CreateJobResponse)
    async def create_job(files: list[UploadFile], count: int = Form(...)) -> CreateJobResponse:
        uploads = [(f.filename or "video.mp4", await f.read()) for f in files]
        job = store.create_job(uploads, count=count)
        return CreateJobResponse(job_id=job.job_id,
                                 sources=[_source_out(s, ok_only=True) for s in job.sources])

    @app.get("/api/jobs", response_model=list[JobSummary])
    def list_jobs() -> list[JobSummary]:
        return [JobSummary(job_id=j.job_id, count=j.count, created_utc=j.created_utc,
                           state=j.state, source_count=len(j.sources))
                for j in store.list()]

    @app.get("/api/jobs/{job_id}", response_model=JobDetail)
    def get_job(job_id: str) -> JobDetail:
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return JobDetail(job_id=job.job_id, count=job.count, created_utc=job.created_utc,
                         state=job.state, sources=[_source_out(s, ok_only=True) for s in job.sources])

    @app.get("/api/jobs/{job_id}/events")
    async def job_events(job_id: str):
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")

        async def gen():
            sent = 0
            while True:
                # drain newly-appended events from the in-memory log
                while sent < len(job.events):
                    yield {"data": json.dumps(event_to_dict(job.events[sent]))}
                    sent += 1
                if job.state == "done" and sent >= len(job.events):
                    yield {"data": json.dumps({"state": "job-done"})}
                    return
                await asyncio.sleep(0.1)

        return EventSourceResponse(gen())

    return app
```

- [ ] **Step 4: Run; verify it passes**

Run: `./.venv/bin/pytest tests/server/test_app.py -q`
Expected: PASS (health + 4 new tests).

- [ ] **Step 5: Lint + commit**

Run: `./.venv/bin/ruff check .` (clean).

```bash
git add variant_maker/server/app.py tests/server/test_app.py
git commit -m "feat(server): job create/list/get routes + SSE progress stream"
```

---

## Task 9: Routes — gallery + diagnostics

**Files:**
- Modify: `variant_maker/server/app.py`
- Modify: `tests/server/test_app.py`

**Interfaces:**
- Routes:
  - `GET /api/gallery` → `list[SourceOut]` — every source across all jobs, each serialized with `ok_only=True` (cards show passed variants only) but `delivered`/`shortfall` intact.
  - `GET /api/diagnostics` → `list[DiagnosticsItem]` — all `best_effort`/`corrupt` variants across jobs.

- [ ] **Step 1: Write failing tests (append to `tests/server/test_app.py`)**

```python
def test_gallery_groups_sources_ok_only(tmp_path):
    client, store = _client(tmp_path, plan={2: "best_effort"})
    job_id = client.post("/api/jobs",
                         files=[("files", ("a.mp4", b"x", "video/mp4"))],
                         data={"count": "3"}).json()["job_id"]
    store.wait(job_id, timeout=5)
    gallery = client.get("/api/gallery").json()
    assert len(gallery) == 1
    assert gallery[0]["delivered"] == 2
    assert gallery[0]["shortfall"] == 1
    assert all(v["status"] == "ok" for v in gallery[0]["variants"])


def test_diagnostics_lists_non_ok(tmp_path):
    client, store = _client(tmp_path, plan={2: "best_effort", 3: "best_effort"})
    job_id = client.post("/api/jobs",
                         files=[("files", ("a.mp4", b"x", "video/mp4"))],
                         data={"count": "3"}).json()["job_id"]
    store.wait(job_id, timeout=5)
    diag = client.get("/api/diagnostics").json()
    assert len(diag) == 2
    assert all(d["status"] == "best_effort" for d in diag)
```

- [ ] **Step 2: Run; verify it fails**

Run: `./.venv/bin/pytest tests/server/test_app.py -k "gallery or diagnostics" -q`
Expected: FAIL — 404 (routes not defined yet).

- [ ] **Step 3: Add routes to `app.py`** (insert before `return app`)

```python
    from .models import DiagnosticsItem

    @app.get("/api/gallery", response_model=list[SourceOut])
    def gallery() -> list[SourceOut]:
        return [_source_out(s, ok_only=True) for s in store.gallery()]

    @app.get("/api/diagnostics", response_model=list[DiagnosticsItem])
    def diagnostics() -> list[DiagnosticsItem]:
        return [DiagnosticsItem(source_id=v.source_id, index=v.index, filename=v.filename,
                                status=v.status, quality=v.quality)
                for v in store.diagnostics()]
```

(Move the `from .models import DiagnosticsItem` to the top-level imports if you prefer; inline shown for locality.)

- [ ] **Step 4: Run; verify it passes**

Run: `./.venv/bin/pytest tests/server/test_app.py -q`
Expected: PASS (all app tests).

- [ ] **Step 5: Lint + commit**

```bash
git add variant_maker/server/app.py tests/server/test_app.py
git commit -m "feat(server): gallery + diagnostics routes"
```

---

## Task 10: Routes — variant file + source file + regenerate

**Files:**
- Modify: `variant_maker/server/jobs.py` (add `find_variant`, `source_in_path_for`, `regenerate`)
- Modify: `variant_maker/server/app.py`
- Modify: `tests/server/test_jobs.py`, `tests/server/test_app.py`

**Interfaces:**
- `JobStore.find_variant(source_id: str, filename: str) -> str | None` — absolute path to a rendered variant file, or `None`.
- `JobStore.source_file(source_id: str) -> str | None` — absolute path to the original uploaded source (for before/after), or `None`.
- `JobStore.regenerate(source_id: str, n: int) -> bool` — synchronously render `n` more variants for an existing source, appending to its `variants` (indices continue after the current max). Returns `False` if `source_id` unknown. (Sync is fine: regenerate is a small, explicit user action.)
- Routes:
  - `GET /api/variants/{source_id}/{filename}` → the mp4 (`FileResponse`, 404 if missing).
  - `GET /api/sources/{source_id}/source` → the original upload (`FileResponse`, 404 if missing).
  - `POST /api/sources/{source_id}/regenerate` (form `n: int`) → `SourceOut` for the updated source (404 if unknown).

- [ ] **Step 1: Write failing JobStore tests (append to `tests/server/test_jobs.py`)**

```python
def test_find_variant_and_source_file(tmp_path):
    store = _store(tmp_path)
    job = store.create_job([("a.mp4", b"orig-bytes")], count=2)
    store.wait(job.job_id, timeout=5)
    src = store.get(job.job_id).sources[0]
    vpath = store.find_variant(src.source_id, src.variants[0].filename)
    assert vpath and vpath.endswith(".mp4")
    spath = store.source_file(src.source_id)
    with open(spath, "rb") as f:
        assert f.read() == b"orig-bytes"


def test_regenerate_appends_variants(tmp_path):
    store = _store(tmp_path)
    job = store.create_job([("a.mp4", b"x")], count=2)
    store.wait(job.job_id, timeout=5)
    src = store.get(job.job_id).sources[0]
    assert store.regenerate(src.source_id, 2) is True
    assert len(src.variants) == 4
    assert [v.index for v in src.variants] == [1, 2, 3, 4]
```

- [ ] **Step 2: Run; verify it fails**

Run: `./.venv/bin/pytest tests/server/test_jobs.py -k "find_variant or regenerate" -q`
Expected: FAIL — `JobStore` has no attribute `find_variant`.

- [ ] **Step 3: Implement the JobStore methods**

Add a `source_id → (job_id, JobSource)` index. In `__init__` add `self._source_index: dict[str, tuple[str, JobSource]] = {}`. In `create_job`, after building each source, register it: `self._source_index[source_id] = (job_id, <that JobSource>)`. Then add:

```python
    def _locate(self, source_id: str):
        return self._source_index.get(source_id)

    def find_variant(self, source_id: str, filename: str) -> str | None:
        loc = self._locate(source_id)
        if loc is None:
            return None
        job_id, _ = loc
        import os
        path = self._ws.variant_path(job_id, source_id, filename)
        return path if os.path.exists(path) else None

    def source_file(self, source_id: str) -> str | None:
        loc = self._locate(source_id)
        if loc is None:
            return None
        job_id, source = loc
        import os
        path = self._ws.source_in_path(job_id, source_id, source.filename)
        return path if os.path.exists(path) else None

    def regenerate(self, source_id: str, n: int) -> bool:
        loc = self._locate(source_id)
        if loc is None:
            return False
        job_id, source = loc
        out_dir = self._ws.source_out_dir(job_id, source_id)
        start = max((v.index for v in source.variants), default=0)
        # Render n more; the runner numbers from 1, so offset indices on the way in.
        result = self._runner.run(
            self._ws.source_in_path(job_id, source_id, source.filename),
            count=n, out_dir=out_dir, source_id=source_id, on_event=lambda e: None,
        )
        for v in result.variants:
            source.variants.append(VariantInfo(
                source_id=source_id, index=start + v.index, filename=v.filename,
                status=v.status, quality=v.quality,
            ))
        return True
```

> **Note on regenerate filenames:** `FakeRunner` and the engine name files `v{index}…`; a regenerate could collide names with the originals (`v01.mp4`). For Stage 1 this is acceptable because regenerate overwrites into the same `out` dir with fresh content and the appended `VariantInfo` uses offset indices for display. If collisions matter later, pass a filename prefix into `Runner.run`. Not needed now (YAGNI).

- [ ] **Step 4: Run; verify it passes**

Run: `./.venv/bin/pytest tests/server/test_jobs.py -q`
Expected: PASS.

- [ ] **Step 5: Write failing app tests (append to `tests/server/test_app.py`)**

```python
def test_serve_variant_and_source_files(tmp_path):
    client, store = _client(tmp_path)
    job_id = client.post("/api/jobs",
                         files=[("files", ("a.mp4", b"orig", "video/mp4"))],
                         data={"count": "1"}).json()["job_id"]
    store.wait(job_id, timeout=5)
    src = client.get(f"/api/jobs/{job_id}").json()["sources"][0]
    fname = src["variants"][0]["filename"]
    sid = src["source_id"]
    assert client.get(f"/api/variants/{sid}/{fname}").status_code == 200
    assert client.get(f"/api/sources/{sid}/source").content == b"orig"
    assert client.get("/api/variants/nope/x.mp4").status_code == 404


def test_regenerate_endpoint(tmp_path):
    client, store = _client(tmp_path)
    job_id = client.post("/api/jobs",
                         files=[("files", ("a.mp4", b"x", "video/mp4"))],
                         data={"count": "2"}).json()["job_id"]
    store.wait(job_id, timeout=5)
    sid = client.get(f"/api/jobs/{job_id}").json()["sources"][0]["source_id"]
    resp = client.post(f"/api/sources/{sid}/regenerate", data={"n": "2"})
    assert resp.status_code == 200
    assert resp.json()["delivered"] >= 2
    assert client.post("/api/sources/nope/regenerate", data={"n": "1"}).status_code == 404
```

- [ ] **Step 6: Run; verify it fails**

Run: `./.venv/bin/pytest tests/server/test_app.py -k "serve_variant or regenerate" -q`
Expected: FAIL — routes 404.

- [ ] **Step 7: Add the file-serving + regenerate routes to `app.py`** (before `return app`)

```python
    from fastapi.responses import FileResponse

    @app.get("/api/variants/{source_id}/{filename}")
    def variant_file(source_id: str, filename: str):
        path = store.find_variant(source_id, filename)
        if path is None:
            raise HTTPException(status_code=404, detail="variant not found")
        return FileResponse(path, media_type="video/mp4", filename=filename)

    @app.get("/api/sources/{source_id}/source")
    def source_file(source_id: str):
        path = store.source_file(source_id)
        if path is None:
            raise HTTPException(status_code=404, detail="source not found")
        return FileResponse(path, media_type="video/mp4")

    @app.post("/api/sources/{source_id}/regenerate", response_model=SourceOut)
    def regenerate(source_id: str, n: int = Form(...)) -> SourceOut:
        loc = store._locate(source_id)
        if not store.regenerate(source_id, n):
            raise HTTPException(status_code=404, detail="source not found")
        _, source = loc
        return _source_out(source, ok_only=True)
```

(Hoist `from fastapi.responses import FileResponse` to the top with the other imports if preferred.)

- [ ] **Step 8: Run; verify it passes**

Run: `./.venv/bin/pytest tests/server/ -q`
Expected: PASS (full server suite).

- [ ] **Step 9: Lint + commit**

Run: `./.venv/bin/ruff check .` (clean).

```bash
git add variant_maker/server/jobs.py variant_maker/server/app.py tests/server/test_jobs.py tests/server/test_app.py
git commit -m "feat(server): variant/source file serving + regenerate"
```

---

## Task 11: CLI entrypoint (`cli.py`)

**Files:**
- Create: `variant_maker/server/cli.py`
- Modify: `tests/server/test_app.py` (smoke test for the app factory used by the CLI)

**Interfaces:**
- Produces `variant_maker.server.cli.main()` — parses `--host`/`--port`/`--data-dir`, builds the default app, and runs uvicorn. Registered as the `variant-server` script (Task 1).
- Produces `variant_maker.server.cli.build_app(data_dir: str) -> FastAPI` — testable factory (no uvicorn).

- [ ] **Step 1: Write the failing test (append to `tests/server/test_app.py`)**

```python
def test_cli_build_app_serves_health(tmp_path):
    from variant_maker.server.cli import build_app
    client = TestClient(build_app(str(tmp_path)))
    assert client.get("/api/health").json() == {"status": "ok"}
```

- [ ] **Step 2: Run; verify it fails**

Run: `./.venv/bin/pytest tests/server/test_app.py -k cli_build_app -q`
Expected: FAIL — `ModuleNotFoundError: variant_maker.server.cli`.

- [ ] **Step 3: Implement `cli.py`**

```python
"""`variant-server` — launch the local control-plane API."""
from __future__ import annotations

import argparse

from fastapi import FastAPI

from .app import create_app
from .jobs import JobStore
from .runner import LocalRunner
from .workspace import Workspace


def build_app(data_dir: str) -> FastAPI:
    return create_app(JobStore(Workspace(data_dir), LocalRunner()))


def main() -> None:
    p = argparse.ArgumentParser(prog="variant-server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--data-dir", default="./.vmdata")
    args = p.parse_args()

    import uvicorn
    uvicorn.run(build_app(args.data_dir), host=args.host, port=args.port)
```

- [ ] **Step 4: Run; verify it passes**

Run: `./.venv/bin/pytest tests/server/test_app.py -k cli_build_app -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add variant_maker/server/cli.py tests/server/test_app.py
git commit -m "feat(server): variant-server CLI entrypoint"
```

---

## Task 12: End-to-end integration test (real engine)

Proves the whole control plane works against the *real* `LocalRunner` + `pipeline.run` on a tiny clip — no mocks. Marked `integration` (needs ffmpeg + libvmaf).

**Files:**
- Create: `tests/server/test_integration.py`

**Interfaces:**
- Consumes: the real `LocalRunner`, `JobStore`, `create_app`, and a fixture clip. Reuse the existing fixture used by `tests/test_pipeline.py` (inspect `tests/conftest.py` / `tests/fixtures/` for the clip fixture name; this test depends on the same one).

- [ ] **Step 1: Identify the existing clip fixture**

Run: `./.venv/bin/python -c "import pathlib; print([p.name for p in pathlib.Path('tests/fixtures').glob('*')])"`
And open `tests/conftest.py` to find the fixture that yields a sample video path (e.g. `sample_clip`). Use that fixture name in Step 2.

- [ ] **Step 2: Write the integration test**

```python
# tests/server/test_integration.py
import pytest
from fastapi.testclient import TestClient

from variant_maker.server.app import create_app
from variant_maker.server.jobs import JobStore
from variant_maker.server.runner import LocalRunner
from variant_maker.server.workspace import Workspace


@pytest.mark.integration
def test_end_to_end_real_engine(tmp_path, sample_clip):  # <-- use the real fixture name
    store = JobStore(Workspace(str(tmp_path)), LocalRunner())
    client = TestClient(create_app(store))

    with open(sample_clip, "rb") as f:
        data = f.read()
    job_id = client.post(
        "/api/jobs",
        files=[("files", ("clip.mp4", data, "video/mp4"))],
        data={"count": "2"},
    ).json()["job_id"]

    assert store.wait(job_id, timeout=300)
    detail = client.get(f"/api/jobs/{job_id}").json()
    src = detail["sources"][0]
    assert src["requested"] == 2
    # at least one variant delivered, and its file is served
    assert src["delivered"] >= 1
    fname = src["variants"][0]["filename"]
    sid = src["source_id"]
    r = client.get(f"/api/variants/{sid}/{fname}")
    assert r.status_code == 200 and len(r.content) > 0

    gallery = client.get("/api/gallery").json()
    assert any(s["source_id"] == sid for s in gallery)
```

- [ ] **Step 3: Run the integration test (requires ffmpeg + libvmaf)**

Run: `./.venv/bin/pytest tests/server/test_integration.py -q -m integration`
Expected: PASS. (If skipped/failing because the fixture name differs, fix the fixture name from Step 1. If ffmpeg lacks libvmaf, `ffmpeg -filters | grep vmaf` will be empty — install an ffmpeg with libvmaf, see engine `CLAUDE.md`.)

- [ ] **Step 4: Run the full suite (unit) to confirm nothing regressed**

Run: `./.venv/bin/pytest -q -m "not integration"`
Expected: PASS (all prior tests + new server suite).

- [ ] **Step 5: Lint + commit**

Run: `./.venv/bin/ruff check .` (clean).

```bash
git add tests/server/test_integration.py
git commit -m "test(server): end-to-end integration over the real engine"
```

---

## Self-Review

**1. Spec coverage** (spec → task):
- FastAPI backend imports `pipeline.run`, background jobs → Tasks 5, 6.
- Streams per-variant progress (rendering → quality-check → re-rolling → done) via SSE → Tasks 3 (engine seam), 8 (SSE route).
- Serves manifest + variant files → Task 10. (Manifest is written by the engine into `out/manifest.json`; served file path available via workspace. A dedicated manifest route is frontend-driven — see Open item below.)
- Filesystem workspace (uploads/outputs/manifests), no DB → Task 4, 6.
- Studio: multiple videos, count per video, one shared config → Task 6 (`create_job` multi-upload, single `count`), Task 8 (multipart).
- Gallery: grouped by source, ok-only, delivered/shortfall → Tasks 6, 9.
- Diagnostics: best_effort/corrupt → Tasks 6, 9.
- Auto-retry cap 3 → existing engine (`max_regen=3` via LocalRunner), visibility via Task 3 `rerolling` events.
- Regenerate shortfall → Task 10.
- Runner seam (no-rewrite, future GPU runner) → Task 5.

**2. Placeholder scan:** No "TBD"/"add error handling"/"similar to" — each step has real code or a real command. ✅

**3. Type consistency:** `VariantEvent` fields identical across `events.py`, `runner.py`, `jobs.py`. `status` values `ok`/`best_effort`/`corrupt` consistent engine→runner→store→routes. `SourceOut`/`VariantOut` field names match the route serializers. `Runner.run` signature identical in protocol, `LocalRunner`, and `FakeRunner`. ✅

**Open item (carry to frontend plan, not a blocker):** the variant-detail panel may want the per-variant manifest entry. The full `manifest.json` is already on disk per source; if the frontend needs it, add `GET /api/sources/{source_id}/manifest` (FileResponse) — trivial, deferred until the frontend confirms it needs more than the `quality` dict already returned on each `VariantOut`.

---

## Execution Handoff

(filled in after user review)
