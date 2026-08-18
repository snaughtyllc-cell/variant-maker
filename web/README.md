# variant-maker control plane — web frontend

Next.js 16 App Router UI for the variant-maker engine.
Pure client of the FastAPI backend via a same-origin dev proxy.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| **Node >= 18.18** | Check with `node -v` |
| **ffmpeg with libvmaf** | Required by the engine; verify with `ffmpeg -filters \| grep vmaf` |
| **Python venv at `./.venv`** | Created from the repo root with `pip install -e ".[server]"` (or the `[dev]` extra). Must expose the `variant-server` entry point. |

---

## Install

```bash
cd web
npm install
```

---

## Running locally

You need both the API (port 8000) and the Next.js dev server (port 3000) running.

### Option A — run both with one command (from the repo root)

```bash
./dev.sh [data-dir]
# data-dir defaults to ./.vmdata
```

The script starts the API in the background and the web dev server in the foreground.
Ctrl-C kills both.

### Option B — run them separately

**Terminal 1 — API:**
```bash
./.venv/bin/variant-server --data-dir <data-dir>
# Listens on http://localhost:8000
```

**Terminal 2 — web:**
```bash
cd web
npm run dev
# Listens on http://localhost:3000
```

---

## Proxy configuration

The environment variable `API_PROXY_TARGET` controls where the frontend routes API
traffic (default: `http://localhost:8000`).

```bash
# web/.env.local
API_PROXY_TARGET=http://localhost:8000
```

It is read in two places:

1. **`next.config.ts` rewrites** — `/api/*` requests made by the browser are forwarded to
   the backend during `npm run dev`.

2. **SSE Route Handler** (`app/api/jobs/[job_id]/events/route.ts`) — the dev-proxy rewrite
   buffers `text/event-stream` before forwarding it, which breaks SSE. This frontend-only
   Route Handler proxies the SSE stream itself so the browser receives events incrementally.
   It reads `API_PROXY_TARGET` at request time, so changing the env var and restarting the
   dev server is all that is needed.

No backend changes are required by the frontend.

---

## Tests

```bash
cd web
npm test
```

Expected output (all 7 suites, 24 tests):

```
Test Files  7 passed (7)
      Tests  24 passed (24)
```

Suites covered: `format`, `api`, `progress`, `useJobProgress`, `files`, `gallery`, `media`.

---

## Production build

```bash
cd web
npm run build
```

Compiles TypeScript, runs Turbopack, and generates the optimised output in `.next/`.
The build must succeed with no type errors before merging.

---

## Screens

| Screen | How to reach it | What it does |
|---|---|---|
| **Studio** | `/` (root) | Drop one or more source videos, set variant count, click Generate. A live progress panel streams rendering events — tiles appear as each variant completes. Reload mid-run to re-attach to the running job. |
| **Gallery** | `/gallery` | Groups completed variants by source video. Cards autoplay on hover. Groups showing fewer variants than requested display a "Regenerate" button to fill the shortfall. |
| **Variant side-panel** | Click any Gallery card | Slide-in panel with a before/after compare slider, a scrub bar that plays both streams in sync, quality metrics from the manifest, a greyed-out Similarity placeholder (Stage 2), and a Download button. |
| **Diagnostics** | `/diagnostics` | Lists failed variants grouped by reason (`below_floor`, `corrupt`, `best_effort`). `best_effort` variants include an Inspect link to the side-panel. |

---

## Stage 2 note (Vercel deployment)

Set `API_PROXY_TARGET` to the deployed FastAPI URL and redeploy the Next.js app to Vercel.
No component or route changes are required — the SSE Route Handler and rewrites both read
the same env var at runtime.

```bash
# In the Vercel project environment variables:
API_PROXY_TARGET=https://api.example.com
```
