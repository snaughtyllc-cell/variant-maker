# Control-Plane Frontend — Stage 1 Design

**Date:** 2026-06-29
**Status:** Approved (brainstorm) — pending spec review
**Scope:** The Next.js frontend for the variant-maker control plane. Built against the **already-shipped, locked** FastAPI in `variant_maker/server/`. No backend changes required.

> Companion specs: [`2026-06-28-control-plane-ui-design.md`](2026-06-28-control-plane-ui-design.md) (product/UX), [`../plans/2026-06-28-control-plane-backend.md`](../plans/2026-06-28-control-plane-backend.md) (the API this builds on). This document is the **frontend** half: visual system, tech architecture, screen builds, and the exact API contract consumed.

---

## 1. Goal

A local, zero-config "smart repurpose" UI: drop video(s) + a count → Generate → watch live progress → browse variants with quality scores and before/after. The AI owns strength and variation; the user owns only **which videos** and **how many**. The frontend talks **only** to the existing API and **ports to Vercel unchanged** in Stage 2 (the frontend↔API contract is the no-rewrite seam).

Four screens: **Studio · Gallery · Diagnostics**, plus a **variant-detail side-panel** that overlays the Gallery.

---

## 2. Visual system (locked)

**Direction: "Studio Dark + a dash of Creator energy"** — option A as the base, a little of option C's neon for accents. A dark neutral canvas keeps the *footage* the brightest thing on screen; neon appears only on actions and progress, never on the canvas, so it stays a pro tool rather than a toy.

### Design tokens
```
--bg:#0a0a0e   --panel:#101018   --panel2:#15151f
--line:#23232f --line2:#2c2c3a
--text:#ececf4 --muted:#8a8aa0   --muted2:#62627a
--violet:#7c5cff (primary)       --violetL:#a78bfa
--cyan:#22d3ee   (live / active accent)
--pink:#ff4d8d   (CTA energy, used sparingly)
--green:#22c55e (pass)  --amber:#f59e0b (re-roll / below-floor)  --red:#f87171 (corrupt)
```
- **Primary action gradient:** `linear-gradient(135deg, var(--violet), var(--pink))` with a soft glow — Generate, Regenerate, primary buttons.
- **Progress gradient:** `linear-gradient(90deg, var(--violet), var(--cyan))` — progress bars, quality meters.
- **Live/active state:** cyan dot + cyan text ("● live", "● rendering…").
- **Status semantics:** green = passed/delivered, amber = re-rolling / below floor (best_effort), red = corrupt.
- **Typography:** system UI stack; weights 600–800 for headings/numbers, 11–13px body, uppercase 11px tracked labels for section headers.
- **Shape:** 9–14px radii, 1px `--line` borders, subtle shadows on hover/active cards.
- **Radii / density:** variant thumbnails are **9:16**; Gallery grid is **8 across** on wide screens (responsive down). The mockups in `.superpowers/brainstorm/.../content/` are the visual reference of record.

---

## 3. Architecture & the no-rewrite seam

Two processes, one contract. The frontend is a pure client of the locked HTTP API.

```
┌─────────────────────┐   /api/* (same-origin via dev proxy)   ┌──────────────────────────┐
│  Next.js (web/)     │  ───────────────────────────────────►  │  FastAPI (variant_maker  │
│  Studio / Gallery   │   HTTP + SSE                            │  .server, port 8000)     │
│  Diagnostics        │  ◄───────────────────────────────────  │  jobs / gallery / files  │
└─────────────────────┘                                        └──────────────────────────┘
```

- **Same-origin via dev proxy (no CORS, no backend change).** A Next.js `rewrites()` rule maps `/api/:path*` → `http://localhost:8000/api/:path*` (target from `API_PROXY_TARGET`, default `http://localhost:8000`). Every API response (including each `file_url` like `/api/variants/{sid}/{fn}`) is therefore reachable from the browser at a relative path, so `<video src={file_url}>` and `EventSource("/api/jobs/{id}/events")` work directly.
- **Why a proxy and not direct calls:** the variant files serve **inline** (`FileResponse(media_type="video/mp4")`, no `Content-Disposition: attachment`) precisely so `<video>` can play them. Keeping the frontend same-origin avoids CORS entirely and keeps the locked backend untouched.
- **Stage-2 port to Vercel:** swap the rewrite target to the deployed API base via env (`API_PROXY_TARGET`) — or a Vercel rewrite — with zero component changes. The same code paths serve local and cloud.
- **No client-side filesystem or engine access.** The frontend knows only the API.

### Known risk to validate early (Task 1 of the plan)
**SSE through the Next dev rewrite must stream un-buffered.** Next's dev proxy generally streams `text/event-stream`, but if buffering is observed, the fallback is a **frontend-only Next.js Route Handler** (`app/api/jobs/[job_id]/events/route.ts`) that `fetch`es the upstream SSE and returns its `ReadableStream` — route handlers stream, so no rewrite buffering and **no backend change**. Plan A = the rewrite; plan B = the route handler; **both are frontend-only**. **Decision: validate the proxy path first with a real `variant-server` before building the progress UI.**

---

## 4. Tech stack

- **Next.js (App Router) + TypeScript.** Ports to Vercel unchanged.
- **Tailwind CSS**, with the §2 tokens wired into `tailwind.config` (CSS variables). Bespoke dark components, hand-rolled.
- **Radix UI primitives** for the few interactive shells that benefit: Dialog/Sheet (side-panel overlay), Popover/DropdownMenu (sort/format menus). Everything else is plain styled markup.
- **lucide-react** for icons.
- **SWR** for GET data (gallery, diagnostics, job detail) — cache + revalidation + `mutate` after Regenerate.
- **Native `EventSource`** for the SSE progress stream (wrapped in a `useJobProgress` hook).
- **Native `<video>`** for all playback (no player library): inline-served mp4s, `preload="metadata"`, first frame as poster, hover-to-play (muted, loop) for cards.

---

## 5. App structure (`variant-maker/web/`)

```
web/
  app/
    layout.tsx                 # TopNav + engine status strip + theme; wraps all pages
    page.tsx                   # Studio (home, "/")
    gallery/page.tsx           # Gallery (+ side-panel overlay, URL-driven)
    diagnostics/page.tsx       # Diagnostics
  components/
    nav/TopNav.tsx  nav/StatusStrip.tsx
    studio/DropZone.tsx  studio/FileList.tsx  studio/VariantStepper.tsx
    studio/GenerateButton.tsx  studio/AdvancedPanel.tsx
    studio/ProgressPanel.tsx  studio/SourceProgressCard.tsx
    gallery/SourceGroup.tsx  gallery/VariantCard.tsx  gallery/GalleryToolbar.tsx
    variant/VariantSheet.tsx  variant/CompareSlider.tsx  variant/ScrubBar.tsx
    variant/QualityPanel.tsx  variant/VariantActions.tsx
    diagnostics/DiagnosticsList.tsx  diagnostics/DiagnosticsRow.tsx
    common/VideoThumb.tsx  common/Badge.tsx  common/ProgressBar.tsx
  lib/
    api.ts        # typed fetchers for every endpoint
    types.ts      # TS mirrors of the API models (§8)
    useJobProgress.ts  # EventSource hook → reduced per-source progress
    useGallery.ts  useDiagnostics.ts  useJobDetail.ts  # SWR hooks
    format.ts     # duration, reason strings, score formatting
  next.config.js  # rewrites() proxy
  tailwind.config.ts  postcss.config.js
  package.json  tsconfig.json
```

- **Navigation:** App Router. Studio = `/`. A persistent run state (see §6) lets a job started on Studio keep streaming while the user visits `/gallery`.
- **Side-panel** is URL-driven: `/gallery?v=<source_id>:<index>` opens the sheet for that variant (deep-linkable, back-button closes). Implemented as a client overlay over the Gallery, not a route swap, so the grid stays mounted behind it.

---

## 6. Live progress (SSE) — the heart of Studio

**Endpoint:** `GET /api/jobs/{job_id}/events` (SSE). Each `data:` line is a JSON `VariantEvent`; a terminal `{"state":"job-done"}` ends the stream. The backend **replays the full event log from the start on every connect**, then tails live — so reconnecting after navigating away or reloading rebuilds the complete picture.

**`useJobProgress(jobId)`** opens an `EventSource`, reduces events, and exposes per-source progress:

```ts
type SourceProgress = {
  source_id: string
  requested: number              // from CreateJobResponse
  delivered: number              // count of done events with status === "ok"
  done: number                   // count of all done events (ok + non-ok)
  inFlight?: { index: number; state: "rendering"|"checking"|"rerolling";
               attempt: number; max_attempts: number }
  variants: VariantTile[]        // built from done events: {index, filename, status, quality, file_url}
}
```

**Reduction rules (event `state` → UI):**
- `rendering` / `checking` → set `inFlight` for that index (cyan "● v16 rendering…").
- `rerolling` (carries `attempt`, `max_attempts`) → amber "↻ v15 re-rolling 2/3".
- `done` (carries `status`, `quality`, `filename`) → append a variant tile; increment `done`, and `delivered` if `status === "ok"`; build `file_url = /api/variants/{source_id}/{filename}`.
- `job-done` → close the stream; mark run complete.

**Behaviors locked by the UI spec:**
- **Two inputs only.** Generate → `POST /api/jobs` (multipart `files[]` + `count`) → `{job_id, sources[]}`; seed `requested` per source from the response, then attach `useJobProgress(job_id)`.
- **Re-rolls are visible** via the `rerolling` events (cap 3).
- **Finished variants appear live in the Studio progress panel** as each `done(ok)` arrives (its `file_url` is already serveable). The **Gallery** page reflects a source once its run completes — the locked API populates `/api/gallery` per-source on completion, not per-variant — so Gallery is revalidated when the run finishes.
- **The run survives leaving the page.** Run identity (`job_id`) is held in a small app-level store (React context / module singleton) + reflected in the URL/session so navigating to Gallery and back re-attaches; a hard reload re-attaches via SSE replay. Optionally seed initial state from `GET /api/jobs/{job_id}` then tail SSE.
- **`jobs=1` server-side** ⇒ events arrive cleanly ordered.

---

## 7. Media playback

No thumbnail/poster endpoint exists, and none is needed:
- **Variant cards & source thumbs** = `<video src={file_url} preload="metadata" muted playsInline>` showing the first frame; **hover** plays (muted, `loop`), mouse-out pauses and resets. Cheap, accurate, no extra assets.
- **Before/after compare** (side-panel) = two stacked `<video>`:
  - bottom layer = variant (`file_url`), top layer = source (`/api/sources/{source_id}/source`) clipped to the slider position (`clip-path: inset(0 calc(100% - X) 0 0)`).
  - a draggable handle sets X; labels SOURCE (left) / VARIANT (right).
  - **Scrub bar** drives a single `currentTime` applied to **both** videos; one play/pause toggles both. The sampler may apply a small speed change, so durations can differ slightly — the compare is a **visual reference, not frame-locked**; clamp `currentTime` to each video's own `duration`.

---

## 8. API contract consumed (locked — exact)

All paths are under the `/api` proxy. **No new endpoints required.**

| Method | Path | Request | Response | Used by |
|---|---|---|---|---|
| POST | `/api/jobs` | multipart: `files[]`, form `count:int` | `201 CreateJobResponse` | Studio Generate |
| GET | `/api/jobs` | — | `JobSummary[]` | (run history; optional) |
| GET | `/api/jobs/{job_id}` | — | `JobDetail` (404) | Studio re-attach / seed |
| GET | `/api/jobs/{job_id}/events` | — | SSE `VariantEvent` … `{"state":"job-done"}` | Studio live progress |
| GET | `/api/gallery` | — | `SourceOut[]` (ok-only variants) | Gallery |
| GET | `/api/diagnostics` | — | `DiagnosticsItem[]` | Diagnostics |
| GET | `/api/variants/{source_id}/{filename}` | — | inline `video/mp4` | cards, compare |
| GET | `/api/sources/{source_id}/source` | — | inline `video/mp4` | compare (before) |
| POST | `/api/sources/{source_id}/regenerate` | form `n:int` | `SourceOut` (404) | Gallery / side-panel Regenerate |

**Model shapes (TS mirrors in `lib/types.ts`):**
```ts
VariantOut   = { index:number; filename:string; status:"ok"|"best_effort"|"corrupt";
                 quality:Quality; file_url:string }
SourceOut    = { source_id:string; filename:string; requested:number; delivered:number;
                 shortfall:number; variants:VariantOut[] }
JobSummary   = { job_id:string; count:number; created_utc:string; state:"running"|"done";
                 source_count:number }
JobDetail    = { job_id:string; count:number; created_utc:string; state:string; sources:SourceOut[] }
CreateJobResponse = { job_id:string; sources:SourceOut[] }
DiagnosticsItem   = { source_id:string; index:number; filename:string;
                      status:"best_effort"|"corrupt"; quality:Quality }
VariantEvent = { source_id:string; index:number;
                 state:"rendering"|"checking"|"rerolling"|"done";
                 attempt:number; max_attempts:number;
                 status:string|null; quality:Quality|null; filename:string|null }
Quality      = { vmaf:number; histogram_ok:boolean; regen_count:number; passed:boolean;
                 spatial_vmaf:number|null; spatial_ok:boolean|null }
```
- **Status mapping:** `ok` → Gallery (delivered). `best_effort` (below VMAF floor) + `corrupt` (spatial-guard reject) → Diagnostics + count as shortfall. `delivered = count(ok)`, `shortfall = requested − delivered` (both already computed server-side on `SourceOut`).
- Gallery & job detail serialize **ok-only** variants into cards but always carry `delivered`/`shortfall`/`requested`.

---

## 9. Screens

### 9.1 Studio (`/`)
Two-column cockpit. **Left:** DropZone (multi-file, browse fallback) → FileList (name + duration), VariantStepper ("Variants each", per-video, shows `N clips → total`), gradient GenerateButton, AdvancedPanel collapsed (Output: **Vertical 1080×1920** default; keep-source available but unsurfaced). **Right:** ProgressPanel — one `SourceProgressCard` per source (thumb, name, `delivered/requested`, progress bar, live status line with visible re-rolls, streamed-variant thumb strip, "N ready" cue). Empty state before a run. Run survives navigation (§6). (Per-variant live view lives here in Studio; the Gallery reflects a source once its run completes — see §6.)

### 9.2 Gallery (`/gallery`)
GalleryToolbar (summary count; **filter: All sources / Has shortfall**; **sort: Newest**). One collapsible `SourceGroup` per source from `GET /api/gallery`: header (thumb, filename, `delivered/requested`, pass summary), then an 8-across grid of `VariantCard`s (9:16, VMAF badge + spatial-pass tick, hover-play, click → side-panel). **Shortfall bar + Regenerate** appears **only** when `shortfall > 0`; hidden on full delivery. Successful variants only.

> **Reveal-on-disk affordances are deferred.** "Open source folder" / "Reveal in Finder" need either a filesystem path in the response or a local reveal endpoint that shells `open` — neither exists in the locked API (it returns URLs, not paths). Stage-1 surfaces **Download** (which works via `file_url`) instead; native reveal is a future local-only backend helper, out of scope here.

### 9.3 Variant detail — side-panel (`/gallery?v=sid:idx`)
Slide-over from the right over a dimmed Gallery. Header: `source · vNN`, "variant k of m", filename, prev/next (steps within the group without closing), close. Body: **CompareSlider** (before/after, §7) + **ScrubBar**; **QualityPanel** (VMAF with pass color, Spatial guard ✓/✗ from `spatial_ok`/`spatial_vmaf`, Histogram from `histogram_ok`, Re-rolls `regen_count`/3); **Similarity** row shown **locked/greyed (`— %`)** with a note — the reserved seam for the Path-B auto-tune brain (keeps layout stable when it lands). **Actions:** Download (`file_url`, force download via `download` attr), Regenerate this one, View manifest entry. (Reveal in Finder is deferred — see §9.2.) Prev/next + the keyboard `←/→` and `Esc`.

> **"View manifest entry"** renders the data the API already returns for the variant (the `VariantOut`: index, filename, status, `quality`) as a small JSON view. The full on-disk `manifest.json` (exact ffmpeg cmd + sampled params) is **not** exposed by the locked API; surfacing it is a trivial future backend add (`GET /api/sources/{sid}/manifest`) and is **out of scope** here (YAGNI for Stage 1).

### 9.4 Diagnostics (`/diagnostics`)
From `GET /api/diagnostics`. Header + summary chips (counts of below-floor vs corrupt). Rows grouped by source: variant index, status badge (amber BELOW FLOOR / red CORRUPT), **plain-language reason + exact metric** derived from `quality` (e.g. `VMAF 84.2 < floor 90`; `Spatial VMAF 22.0 < corruption floor`), exhausted re-roll count (↻ 3/3), per-row actions (Inspect / Manifest / **Regenerate**). **Inspect** is enabled only for `best_effort` (the file is on disk and serveable via `file_url`) and opens the same CompareSlider for that single variant — no group prev/next. `corrupt` rows show a dead thumb (file torn/absent) and disable Inspect. Normal state = empty, with a friendly "Nothing failed — all variants delivered."

---

## 10. State & data fetching

- **GET data** (gallery, diagnostics, job detail, job list) via **SWR**; `mutate` the gallery/source after a Regenerate resolves.
- **Live run state** via `useJobProgress` (SSE), held in an app-level store keyed by `job_id` so it persists across route changes within the session.
- **Regenerate** (`POST …/regenerate`) returns the updated `SourceOut`; optimistic-update the group/panel then revalidate.
- **Errors:** API failures surface as inline toasts/banners (upload rejected, job 404, file 404). Network loss on SSE → auto-reconnect (EventSource default) which re-replays cleanly.
- **Loading:** skeletons for grids, a spinner row for in-flight progress cards.

---

## 11. Out of scope (Stage 1)

- Drive / OAuth / farm screens, auth, DB (filesystem only — Stage 2).
- Per-video config overrides within a run (one shared config).
- Path-B similarity measurement / auto-tune (Similarity stays a locked, greyed seam).
- Any detector / platform-spoofing logic (forbidden by engine scope guards).
- Full on-disk manifest exposure / a manifest route (deferred backend nicety).
- Any backend change. The SSE-through-proxy risk (§3) is handled **frontend-only** (the rewrite, or a Next.js Route Handler if it buffers) — no backend change under any branch.

---

## 12. Stage-2 seams (built now, used later)

- Frontend ports to Vercel by swapping the proxy/env target — no component changes.
- `file_url` indirection means storage can move (filesystem → object store) without touching the UI.
- The greyed **Similarity** row + QualityPanel layout already reserve space for the Path-B readout.
- `platforms.PLATFORMS` placeholders → the AdvancedPanel format selector is ready for real per-platform options.

---

## 13. Decisions locked in this brainstorm

1. **Aesthetic:** Studio Dark base + a dash of Creator-energy neon (A+C). Tokens in §2.
2. **Studio layout:** left cockpit / right live progress (side-by-side), variant thumbs shown inside progress cards.
3. **Gallery:** filter = All / Has-shortfall; **8 across**; Regenerate only on shortfall.
4. **Side-panel:** keep the **greyed Similarity** row visible (reserve the seam; no layout jump later).
5. **Diagnostics:** grouped by source, plain-language reason + exact metric, per-row Regenerate.
6. **Tech:** Next.js App Router + TS + Tailwind + Radix primitives + SWR + native EventSource/`<video>`; **same-origin dev proxy** (no CORS, no backend change); `web/` inside the existing repo.
7. **Manifest view** scoped to the data the API already returns; no new endpoint.
