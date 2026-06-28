# Control-Plane UI — Stage 1 Design

**Date:** 2026-06-28
**Status:** Approved (brainstorm) — pending spec review
**Scope:** Stage 1 of the variant-maker control plane. Local, zero-config UI over the existing engine.

---

## 1. Goal

A local, **zero-config "smart repurpose"** UI on top of the existing variant-maker engine:
drop a video (or several) → the AI generates distinct variants → browse them with quality
scores and before/after. The UI is deliberately built so it lifts to Vercel + a database +
a cloud worker later **with no rewrite**.

This is **Stage 1** of a staged build. Stage 2 (Drive farm, auth, cloud) is out of scope here
but the architecture is chosen so Stage 1 is not throwaway.

---

## 2. Architecture

Two processes, one filesystem workspace. The frontend↔API contract is the "no-rewrite" seam.

```
┌─────────────────┐      HTTP + WS/SSE        ┌──────────────────────────┐
│  Next.js (UI)   │  ───────────────────────► │  FastAPI (backend)       │
│  Studio         │                           │  imports                 │
│  Gallery        │  ◄─── progress stream ───  │  variant_maker.pipeline  │
│  Diagnostics    │      manifests + files    │  runs jobs in background │
└─────────────────┘                           └──────────────────────────┘
                                                        │
                                              filesystem workspace
                                          uploads / outputs / manifests
```

- **FastAPI backend**
  - Imports `variant_maker.pipeline.run(config) -> Manifest` and runs jobs in the background.
  - **Streams per-variant progress** (states: `rendering` → `quality-check` →
    `done` | `failed` | `re-rolling`) over **SSE** (one-way server→client; simplest fit for
    progress, no client→server channel needed). The exact transport is the implementation
    plan's to finalize, but SSE is the default unless a reason to use WS emerges.
  - Serves manifests and the rendered variant files.
  - **Becomes the cloud worker API in Stage 2** — not throwaway scaffolding.
- **Next.js frontend**
  - Talks **only** to that API (no direct filesystem or engine access).
  - **Ports to Vercel verbatim** in Stage 2.
- **Storage (Stage 1):** filesystem workspace only — uploads, outputs, manifests. **No DB yet.**
  The directory layout is the precursor to the Stage-2 DB schema.

### Engine seams already available (do not rebuild)
- `pipeline.run(config) -> Manifest`
- Per-variant manifest entry: `quality={vmaf, spatial_ok, spatial_vmaf, histogram_ok, status}` + `filename`
- `presets.PRESETS` (subtle/medium/strong distortion budgets), `platforms.PLATFORMS` (output geometry)

---

## 3. Core product model

**The AI owns strength and variation. The user owns only "which videos" and "how many."**

- A "variant" is a genuinely distinct, original-quality render of the source — not a degraded
  re-encode. The engine achieves this with **zero-mean, budget-capped randomized adjustments**
  per variant (crop/rotate/brightness/contrast/saturation/grain/speed/etc.), drawn by the sampler.
- The user does **not** set color, strength, or recipe. There is **no Recipes page**.
- The **distortion budget** is the single lever that controls how far a variant moves from the
  source. The north-star objective is **≤35% similarity to the source** per variant.

### Path A vs Path B (same UI, smarter brain)
- **Path A — Stage 1 (this spec):** the budget is a **single configurable default preset**
  (starting at `medium`, a server-side constant), applied automatically to every variant.
  The engine moves each variant "about this much" but does **not** yet measure similarity or
  self-correct. Delivers the zero-config experience immediately.
- **Path B — the real destination (next stage, not built here):** the engine **measures** each
  finished variant's similarity to the source and **self-tunes the budget** until it lands at
  **≤35% similarity** before the user sees it. The UI does not change — only the brain underneath.

### Explicit scope guard
Per the engine's own `CLAUDE.md`: this is **not** a detector, **not** a platform-spoofing engine.
No detector-beating or platform-evasion logic is in scope. The objective is creative-quality
repurposing measured by a similarity target, not bypassing any platform system.

---

## 4. Screens

Navigation: **Studio · Gallery · Diagnostics** (top bar + engine/GPU status strip).

### 4.1 Studio — the run cockpit
Zero-config. Two inputs total.
- **Drop zone** for one or more local videos (browse fallback). Lists selected files with duration.
- **"Variants each"** count field. Count is **per video** (drop 2 clips, type 20 → 20 each = 40).
- **Generate** button.
- **Advanced (collapsed):** output format, defaulting to **vertical** (1080×1920). `keep-source`
  available but not surfaced by default.
- **Live progress** (right side / below): one card per source video with a progress bar, a
  `done/requested` count, and a live status line. **Auto-retry is visible**, e.g.
  `v04 re-rolling 2/3`. Finished variants stream to the Gallery as they pass. **The run survives
  leaving the page** (the backend owns it).

One **shared config per run** (all videos in a run use the same settings). No per-video overrides
in Stage 1.

### 4.2 Gallery — browse results (separate page)
- Results **grouped by source video**: one collapsible group per source clip, whether the run was
  a single video or a batch. All groups on one scrollable page.
- **Successful variants only.** Failed variants never appear here.
- **Group header:** source filename, `delivered / requested` count, pass summary, "open source
  folder" shortcut.
- **Shortfall line + Regenerate** appears **only when** the delivered count is below the requested
  count (after auto-retry exhausted). Hidden on a full delivery.
- **Filter** (all / passed) + **sort** (newest, etc.) across all sources.
- **Per-group display:** grid of variant cards (default). Each card shows VMAF + spatial pass badge.

### 4.3 Variant detail — side panel
Clicking a variant card opens a **side panel** sliding in from the right (gallery stays visible).
- **Before / after** of source vs variant, with a **compare slider** and a **scrub bar**.
- **Quality panel:** VMAF, spatial-guard, histogram.
- **Actions:** Download · Reveal in Finder · Regenerate this one · View manifest · prev/next
  (steps through the group without closing).
- **Similarity %** is **parked** in Stage 1 (no measurement yet); becomes a first-class readout
  when Path B lands.

### 4.4 Diagnostics — back-end failures page
- Lists the **genuinely failed** variants (only those that exhausted the retry cap) with the
  failure reason (e.g. spatial-corruption fail, quality below floor).
- Out of the main workflow's way; consulted only when you want to understand a failure.

---

## 5. Key behaviors

- **AI decides strength + variation** (Path A: smart default; Path B: auto-tune to ≤35% similarity).
- **Auto-retry to hit count:** when a variant fails its quality/spatial check, the engine re-rolls
  that slot, **cap 3 re-rolls per slot**. Only a slot still failing after the cap becomes a real
  "failure" → surfaces in Diagnostics and produces a Gallery shortfall line. Target outcome:
  "20 requested = 20 delivered" is the normal case.
- **Count = per video**, one shared config per run.
- **Progress states** streamed per variant: `rendering` → `quality-check` → `done` | `failed`
  | `re-rolling (n/3)`.

---

## 6. Out of scope (Stage 1)

- Drive / OAuth / farm screens (Stage 2).
- Database (filesystem only in Stage 1).
- Per-video config overrides within a run.
- The Path-B auto-tune brain (similarity measurement + budget self-tuning).
- Similarity % display (parked until Path B).
- Any detector / platform-spoofing logic (forbidden by engine scope guards).

---

## 7. Stage-2 seams (built in now, used later)

- FastAPI backend = the future cloud worker API.
- Next.js frontend = ports to Vercel unchanged.
- Filesystem workspace layout = precursor to the DB schema.
- `platforms.PLATFORMS` placeholders (tiktok/reels/shorts currently identical) = ready for
  real per-platform specs without a rewrite.
- `platform_result` manifest slot remains reserved.
