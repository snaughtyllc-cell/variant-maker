# VaryForge Uniqueness Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local uniqueness gate (pHash + histogram), light fingerprint upgrades (crop offset + trim split), one creative escalate, platform_result labeling, and ZIP download — so light-polish variants clear upload-time duplicate checks more reliably without claiming platform guarantees.

**Architecture:** Keep quality (`quality.py`) and uniqueness as sibling gates. New `uniqueness.py` scores difference; `pipeline.run` raises strength within `medium`, then one `strong` escalate; manifest + API expose scores/`platform_result`; web polls job detail (SSE stays best-effort behind RunPod proxy) and Gallery marks outcomes + ZIP.

**Tech Stack:** Python 3.11+, existing ffmpeg/ffprobe, pytest, ruff; FastAPI control plane; Next.js web. No new heavy ML deps — uniqueness uses ffmpeg frame extracts + pure-Python aHash/pHash.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-14-uniqueness-loop-design.md` (approved).
- **No “undetectable / guaranteed pass” copy** in UI or docs.
- **Light → preset `medium`; creative escalate → preset `strong` (exactly one).**
- **Defaults:** `uniqueness_target=0.35`, uniqueness strength ladder `[1.0, 1.25, 1.5]` then one strong @ `1.0`; `max_uniq_raises=2` (three light attempts total).
- **Quality floor unchanged** — never skip VMAF/histogram to chase uniqueness.
- **platform_result values:** `null` | `passed` | `duplicate_reject` | `unknown` (replace legacy manifest comments of `pass`/`fail`).
- **Progress states (additive):** existing `rendering|checking|rerolling|done` plus `uniqueness` and `escalating`.
- **TDD:** failing test → implement → green → commit per task.
- **Engine stays offline-capable:** no FastAPI imports in core; uniqueness uses stdlib + ffmpeg only.
- Run tests: `./.venv/bin/pytest -q`; lint: `./.venv/bin/ruff check .`

---

## File Structure

**Create**
- `variant_maker/uniqueness.py` — frame sample + score
- `tests/test_uniqueness.py`
- `tests/test_uniqueness_pipeline.py` — escalation path with fakes
- `web/lib/zip.ts` (or inline in API route) — client ZIP helper if server ZIP preferred see Task 6

**Modify**
- `variant_maker/presets.py` — document/keep medium/strong; no new preset required
- `variant_maker/sampler.py` — `crop_x_frac`, `crop_y_frac`, `trim_end_s`
- `variant_maker/filtergraph.py` — apply crop x/y + end trim
- `variant_maker/pipeline.py` — uniqueness loop + escalate
- `variant_maker/manifest.py` — new VariantRecord fields
- `variant_maker/server/events.py` — new states
- `variant_maker/server/models.py` / `app.py` / `jobs.py` / `runner.py` — fields + platform_result + ZIP
- `web/lib/types.ts`, `progress.ts`, `api.ts`, Studio/Gallery components

**Tests also touch**
- `tests/test_sampler.py`, `tests/test_filtergraph.py`, `tests/test_pipeline.py` / events
- `tests/server/test_app.py`

---

### Task 1: `uniqueness.py` metric

**Files:**
- Create: `variant_maker/uniqueness.py`
- Create: `tests/test_uniqueness.py`

**Interfaces:**
- Produces:
  - `METRIC_VERSION = "phash_hist_v1"`
  - `extract_gray_frames(path: str, *, n: int = 10, size: int = 32) -> list[bytes]`  
    Each frame: `size*size` raw grayscale bytes (row-major).
  - `ahash(frame: bytes, size: int = 32) -> int` — 64-bit average hash from 8×8 mean downsample of `size` gray frame.
  - `histogram_distance(a: bytes, b: bytes) -> float` — ∈ `[0, 1]`
  - `score_uniqueness(src_path: str, variant_path: str, *, n_frames: int = 10, target: float | None = None) -> dict`  
    Returns at least:  
    `{ "uniqueness": float | None, "uniqueness_status": "ok"|"below_target"|"unknown", "uniqueness_metric": METRIC_VERSION, "uniqueness_target": float | None }`  
    If `target` is None, `uniqueness_status` is `"ok"` when score computed, else `"unknown"` on failure. If `target` set: `"ok"` when `uniqueness >= target`, else `"below_target"`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_uniqueness.py
import os, subprocess, tempfile
from variant_maker import uniqueness

def _tiny_mp4(path, *, color="black"):
    # 1s 64x64 solid via lavfi
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=64x64:d=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", path,
    ], check=True, capture_output=True)

def test_identical_videos_score_near_zero():
    with tempfile.TemporaryDirectory() as d:
        a = os.path.join(d, "a.mp4"); b = os.path.join(d, "b.mp4")
        _tiny_mp4(a); _tiny_mp4(b)
        r = uniqueness.score_uniqueness(a, b, n_frames=4)
        assert r["uniqueness_metric"] == "phash_hist_v1"
        assert r["uniqueness"] is not None and r["uniqueness"] < 0.05

def test_different_colors_score_higher():
    with tempfile.TemporaryDirectory() as d:
        a = os.path.join(d, "a.mp4"); b = os.path.join(d, "b.mp4")
        _tiny_mp4(a, color="black"); _tiny_mp4(b, color="white")
        r = uniqueness.score_uniqueness(a, b, n_frames=4, target=0.35)
        assert r["uniqueness"] > 0.2
        assert r["uniqueness_status"] in ("ok", "below_target")

def test_missing_file_unknown():
    r = uniqueness.score_uniqueness("/nope/a.mp4", "/nope/b.mp4")
    assert r["uniqueness"] is None and r["uniqueness_status"] == "unknown"
```

- [ ] **Step 2: Run tests — expect FAIL (module missing)**

```bash
./.venv/bin/pytest tests/test_uniqueness.py -v
```

- [ ] **Step 3: Implement `variant_maker/uniqueness.py`**

Implementation notes (must match interfaces above):
- Extract frames with ffmpeg:  
  `ffmpeg -v error -i PATH -vf "fps=N/DURATION,scale=SIZE:SIZE,format=gray" -frames:v N -f rawvideo -`
  For short clips use `fps=n_frames/max(duration,0.1)` via ffprobe duration, or select frames with `select`/`eq(n\,...)`. Prefer: probe duration, then for `i in 0..n-1` extract one frame at `t = (i+0.5)/n * duration` with `-ss` + `-frames:v 1` to raw gray `size×size`.
- `ahash`: reshape to size×size, box to 8×8 means, threshold vs mean → 64-bit int.
- Hamming distance between hashes / 64 → phash component.
- Histogram: 16-bin luma hist on each frame, mean L1 distance / 2 → hist component ∈ `[0,1]`.
- Combine: `uniqueness = 0.7 * mean_phash + 0.3 * mean_hist` (clip to `[0,1]`).
- On any OSError/CalledProcessError/empty frames → return null/`unknown`.

- [ ] **Step 4: Run tests — expect PASS**

```bash
./.venv/bin/pytest tests/test_uniqueness.py -v
./.venv/bin/ruff check variant_maker/uniqueness.py tests/test_uniqueness.py
```

- [ ] **Step 5: Commit**

```bash
git add variant_maker/uniqueness.py tests/test_uniqueness.py
git commit -m "feat(uniqueness): add phash+histogram uniqueness scorer"
```

---

### Task 2: Crop offset + trim end split (fingerprint axes)

**Files:**
- Modify: `variant_maker/sampler.py`
- Modify: `variant_maker/filtergraph.py`
- Modify: `tests/test_sampler.py`, `tests/test_filtergraph.py`

**Interfaces:**
- `sample(...)` video dict gains:
  - `crop_x_frac: float` ∈ `[0, 1]` (default calm `0.5`)
  - `crop_y_frac: float` ∈ `[0, 1]` (default calm `0.5`)
  - `trim_end_s: float` ≥ `0` (calm `0.0`), drawn like `trim_s` from same preset `trim_s` range independently (unbudgeted, same as `trim_s`)
- `build_video_filters` / `build_audio_filters`:
  - Crop: when `crop_keep < 1`, emit  
    `crop=iw*K:ih*K: (iw-iw*K)*X : (ih-ih*K)*Y`  
    with `K=crop_keep`, `X=crop_x_frac`, `Y=crop_y_frac` (ffmpeg accepts expressions).
  - Trim start unchanged via `trim_s`; add end trim when `trim_end_s > 0`:  
    After start trim, use `trim=end_frame` **or** prefer duration-based:  
    `trim=start=TS:end=DUR-TE` requires duration — **use SourceInfo.duration_s** in `build_video_filters` (already has `src`).  
    Video: if both: `trim=start=TS:end={src.duration_s - TE}` then `setpts`.  
    If only end: `trim=end=...`. Mirror with `atrim` on audio.
  - Quality-neutral dict in `quality.py` (`_QUALITY_NEUTRAL`) must also neutralize new geometry axes: set `crop_x_frac=0.5`, `crop_y_frac=0.5`, `trim_end_s=0.0` when building quality proxy params (extend wherever quality copies/neutralizes params — update `quality.py` helpers that zero crop/trim/speed).

- [ ] **Step 1: Failing sampler test**

```python
def test_sample_includes_crop_offset_and_trim_end():
    from variant_maker.presets import MEDIUM
    from variant_maker.sampler import sample
    p = sample(MEDIUM, seed=1)
    assert 0.0 <= p["video"]["crop_x_frac"] <= 1.0
    assert 0.0 <= p["video"]["crop_y_frac"] <= 1.0
    assert p["video"]["trim_end_s"] >= 0.0
```

- [ ] **Step 2: Failing filtergraph test**

```python
def test_crop_uses_xy_offset():
    params = make_params(video={"crop_keep": 0.95, "crop_x_frac": 0.0, "crop_y_frac": 1.0, "trim_s": 0.0, "trim_end_s": 0.0})
    vf = filtergraph.build_video_filters(params, make_src(), REELS)
    assert "crop=iw*0.9500:ih*0.9500" in vf
    assert "(iw-iw*0.9500)*0.0000" in vf or "*0.0" in vf  # x at 0
```

Update `make_params` defaults to include `crop_x_frac=0.5`, `crop_y_frac=0.5`, `trim_end_s=0.0`. Update golden `EXPECTED_VF` if centered crop string changes (centered = `*0.5000`).

- [ ] **Step 3: Implement sampler + filtergraph (+ quality neutral)**

- [ ] **Step 4: `./.venv/bin/pytest tests/test_sampler.py tests/test_filtergraph.py tests/test_color.py -q` PASS; ruff clean**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(fingerprint): crop offset + head/tail micro-trim"
```

---

### Task 3: Pipeline uniqueness loop + manifest fields

**Files:**
- Modify: `variant_maker/manifest.py`
- Modify: `variant_maker/pipeline.py`
- Modify: `variant_maker/server/events.py` (STATES)
- Create: `tests/test_uniqueness_pipeline.py`
- Modify: existing pipeline/event tests as needed

**Interfaces:**
- `VariantRecord` gains fields (defaults shown):

```python
uniqueness: float | None = None
uniqueness_status: str | None = None  # ok|below_target|unknown
uniqueness_metric: str | None = None
uniqueness_target: float | None = None
preset_used: str | None = None
strength_final: float | None = None
escalated: bool = False
# platform_result already exists; values become passed|duplicate_reject|unknown|None
```

- `pipeline.run` config keys:
  - `uniqueness_target: float = 0.35`
  - `allow_creative_escalate: bool = True`
  - `uniq_strengths: list[float] = [1.0, 1.25, 1.5]` (optional override)
- Loop per variant (replaces single `regen_until_pass` only for the outer uniqueness policy; **quality regen stays inside each attempt**):

```
light_preset = get_preset(config["preset"])  # default medium from runner
for strength in uniq_strengths:
    emit("rendering"...); render+quality via existing attempt()/regen_until_pass
    emit("uniqueness", index=i)
    u = score_uniqueness(src.path, path, target=uniqueness_target)
    if u["uniqueness_status"] in ("ok", "unknown") and quality_passed:
        keep; break
    # below_target + quality ok → try next strength
else:
    if allow_creative_escalate:
        emit("escalating", index=i)
        strong = get_preset("strong")
        # one attempt at strength 1.0 with strong preset (quality regen allowed)
        ...
        escalated=True
    finalize status ok|best_effort as today; attach uniqueness fields
```

- Emit `done` with filename/status/quality as today; uniqueness fields go on `VariantRecord` (and later API). Optionally include uniqueness summary inside `quality` dict **only if** needed for SSE — prefer VariantRecord + job store fields, not overloading quality.

- [ ] **Step 1: Failing unit test with monkeypatches (no ffmpeg uniqueness)**

```python
# tests/test_uniqueness_pipeline.py
def test_escalates_to_strong_when_light_below_target(monkeypatch, tmp_path):
    # monkeypatch uniqueness.score_uniqueness to return below_target twice then ok
    # monkeypatch render_variant / quality.passes_guard to always pass
    # run pipeline with count=1, uniqueness_target=0.35
    # assert record.escalated is True and record.preset_used == "strong"
```

Also test: when first uniqueness `ok`, `escalated is False` and `preset_used == "medium"`.

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement manifest fields + pipeline loop + STATES tuple update**

Update `variant_maker/server/events.py`:

```python
STATES = ("rendering", "checking", "rerolling", "uniqueness", "escalating", "done")
```

Update LocalRunner defaults: keep `preset="medium"`; pass `uniqueness_target=0.35`, `allow_creative_escalate=True` through `pipeline.run` config.

- [ ] **Step 4: pytest targeted + full engine suite subset PASS**

```bash
./.venv/bin/pytest tests/test_uniqueness_pipeline.py tests/test_pipeline_events.py tests/test_uniqueness.py -q
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(pipeline): uniqueness gate with one creative escalate"
```

---

### Task 4: API — expose fields, platform_result, ZIP

**Files:**
- Modify: `variant_maker/server/models.py`
- Modify: `variant_maker/server/jobs.py` (`VariantInfo`, `on_event` recording, `set_platform_result`)
- Modify: `variant_maker/server/app.py`
- Modify: `variant_maker/server/runner.py` (map new VariantRecord fields into VariantResult if needed)
- Modify: `tests/server/test_app.py`, `tests/server/fakes.py`

**Interfaces:**
- Extend `VariantOut`:

```python
class VariantOut(BaseModel):
    index: int
    filename: str
    status: str
    quality: dict
    file_url: str
    uniqueness: float | None = None
    uniqueness_status: str | None = None
    uniqueness_metric: str | None = None
    uniqueness_target: float | None = None
    preset_used: str | None = None
    strength_final: float | None = None
    escalated: bool = False
    platform_result: str | None = None
```

- `VariantInfo` in jobs.py mirrors these fields; populate from runner results **and** on each `done` event if runner streams partials.
- `POST /api/variants/{source_id}/{index}/platform-result`  
  Body: `{"result": "passed"|"duplicate_reject"|"unknown"}`  
  Updates in-memory variant + rewrites `manifest.json` on disk if present (`platform_result` field).  
  Returns updated `VariantOut`.
- `GET /api/sources/{source_id}/zip` → `FileResponse` application/zip of all `status=="ok"` variant files for that source (temp zip in workspace). Empty → 404.

- [ ] **Step 1: Failing API tests with FakeRunner returning uniqueness fields**

```python
def test_platform_result_roundtrip(client):
    # create job via fake → mark passed → getJob shows platform_result

def test_zip_contains_ok_variants(client):
    # create finished job → GET zip → zipfile namelist matches filenames
```

- [ ] **Step 2: Implement models/jobs/app**

- [ ] **Step 3: `./.venv/bin/pytest tests/server/ -q` PASS**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(server): uniqueness fields, platform_result, source ZIP"
```

---

### Task 5: Web — types, progress reducer, API client

**Files:**
- Modify: `web/lib/types.ts`
- Modify: `web/lib/progress.ts`
- Modify: `web/lib/api.ts`
- Modify: `web/lib/__tests__/progress.test.ts`
- Modify: `web/lib/useJobProgress.ts` (already polls getJob — map new fields into tiles)

**Interfaces:**
- Extend `VariantEvent.state` with `"uniqueness" | "escalating"`.
- `reduceEvent`: treat `uniqueness`/`escalating` like in-flight states (same shape as checking).
- `VariantOut` / tiles show `uniqueness`, `escalated`, `platform_result`.
- API:
  - `setPlatformResult(sourceId, index, result)`
  - `sourceZipUrl(sourceId) => `/api/sources/${sourceId}/zip``

- [ ] **Step 1: Failing vitest for new states**

```ts
it("tracks uniqueness inFlight", () => {
  let r = initRun([{ source_id: "s", filename: "a.mp4", requested: 1 }]);
  r = reduceEvent(r, { source_id: "s", index: 1, state: "uniqueness", attempt: 0, max_attempts: 0, status: null, quality: null, filename: null });
  expect(r.bySource.s.inFlight?.state).toBe("uniqueness");
});
```

- [ ] **Step 2: Implement types/progress/api**

- [ ] **Step 3: `cd web && npm test` PASS**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(web): uniqueness progress states + API helpers"
```

---

### Task 6: Web — Studio defaults, Gallery labels, ZIP button

**Files:**
- Modify: `web/app/page.tsx` — default `perVideo` **8**; optional escalate toggle later can be AdvancedPanel checkbox defaulting true (wire to API when createJob accepts flags — if createJob Form has no flags yet, add optional `allow_creative_escalate` + server create_job Form field defaulting true)
- Modify: Gallery / `VariantActions` / side panel — Passed / Duplicate rejected buttons; ZIP download link
- Modify: Progress cards — show uniqueness score + escalated badge + best_effort warning copy (**never** “undetectable”)

**create_job Form extension (if not done in Task 4):**
- `allow_creative_escalate: bool = Form(True)` passed into runner/pipeline config.

- [ ] **Step 1: Wire UI actions calling `setPlatformResult`; ZIP `<a href={sourceZipUrl(id)} download>`**

- [ ] **Step 2: Manual smoke locally**

```bash
./.venv/bin/variant-server --data-dir ./.vmdata &
cd web && npm run dev
# upload short clip, count 3, confirm uniqueness states + gallery mark + zip
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(web): Studio uniqueness defaults, gallery labels, ZIP"
```

---

### Task 7: Deploy notes + Pod restart checklist (ops, no new feature)

**Files:**
- Modify: `deploy/pod/README.md` — uniqueness release smoke steps; note SSE may still buffer; polling shows progress; stop Pod when idle.

- [ ] **Step 1: Document**

```markdown
## Uniqueness smoke (after pull)
1. Start pod services (WEB_PORT=7860)
2. Generate 3 variants Light
3. Confirm uniqueness scores in Gallery
4. Mark one Passed / one Duplicate rejected
5. Download ZIP
```

- [ ] **Step 2: Commit**

```bash
git commit -m "docs(pod): uniqueness smoke checklist"
```

---

## Spec coverage check

| Spec requirement | Task |
|------------------|------|
| uniqueness.py pHash+hist | 1 |
| crop offset + trim split | 2 |
| quality/uniqueness sibling gates + escalate once | 3 |
| manifest fields + metric version | 3 |
| platform_result API | 4 |
| ZIP | 4+6 |
| Progress states uniqueness/escalating | 3+5 |
| Studio Light/8/escalate | 6 |
| Gallery label + scores | 6 |
| No guarantee copy | 6 + Global Constraints |
| Tier-2 out of scope | — (not scheduled) |

## Open points pinned by this plan

- `uniqueness_target` default **0.35**
- Light strengths **`[1.0, 1.25, 1.5]`** then one **strong@1.0**
- Creative = preset **`strong`**
- Additive event states **`uniqueness`**, **`escalating`**
- ZIP **in this release** (Task 4+6)
