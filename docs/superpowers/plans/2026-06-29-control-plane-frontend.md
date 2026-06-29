# Control-Plane Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Next.js (App Router) frontend for the variant-maker control plane — Studio · Gallery · variant side-panel · Diagnostics — against the already-shipped, locked FastAPI in `variant_maker/server/`, with zero backend changes.

**Architecture:** A standalone Next.js app in `variant-maker/web/` that is a pure client of the locked HTTP API. It reaches the API same-origin through a Next `rewrites()` dev proxy (`/api/* → :8000`), so there is no CORS and `<video>`/`EventSource` work against relative URLs. Unit-testable logic (API client, formatters, the SSE progress reducer, pure UI helpers) is built test-first with Vitest; visual components are built with the frontend-design skill and verified against the committed mockups via the fwr screenshot-compare loop.

**Tech Stack:** Next.js (App Router) + TypeScript, Tailwind CSS, Radix UI primitives (Dialog/Popover/DropdownMenu), lucide-react, SWR, native `EventSource` + `<video>`. Tests: Vitest + @testing-library/react + jsdom.

## Global Constraints

- **Spec of record:** `docs/superpowers/specs/2026-06-29-control-plane-frontend-design.md`. Every task implicitly inherits it.
- **Locked API — do NOT change the backend, ever.** Build only against the endpoints/models in spec §8. If SSE buffers through the Next dev rewrite, the fallback is a **frontend-only** Next.js Route Handler that streams the proxied SSE (Tasks 1/6) — there is **no** sanctioned backend change under any branch.
- **App location:** everything lives under `variant-maker/web/`. Run commands from there unless stated. Node ≥ 18.18 (Next requirement).
- **Same-origin proxy:** all API calls use **relative** `/api/...` paths (never `http://localhost:8000` in component code). The proxy target is `API_PROXY_TARGET` (default `http://localhost:8000`).
- **Design tokens (verbatim, spec §2):** `--bg:#0a0a0e --panel:#101018 --panel2:#15151f --line:#23232f --line2:#2c2c3a --text:#ececf4 --muted:#8a8aa0 --muted2:#62627a --violet:#7c5cff --violetL:#a78bfa --cyan:#22d3ee --pink:#ff4d8d --green:#22c55e --amber:#f59e0b --red:#f87171`. Primary CTA gradient `135deg violet→pink`; progress gradient `90deg violet→cyan`; live = cyan; pass=green, reroll/below-floor=amber, corrupt=red. Variant media is **9:16**; Gallery grid **8 across** on wide screens.
- **Status mapping (verbatim):** `ok` → delivered/Gallery; `best_effort` (VMAF below floor) + `corrupt` (spatial-guard reject) → Diagnostics + shortfall. `delivered=count(ok)`, `shortfall=requested−delivered` (already on `SourceOut`). VMAF floor = **90**; corruption is reported via `spatial_ok===false`.
- **TDD where unit-testable; screenshot-compare where visual.** Logic tasks: red→green→commit with Vitest. Visual tasks: invoke `frontend-design`, then the `anthropic-skills:fwr` screenshot-compare loop against the named committed mockup until it matches; commit. Both are real gates.
- **Commit after every task** (and at the green points within a task). Work on branch `tier1`. **Do not push** (the user pushes).
- **Visual oracle:** the committed mockups in `docs/superpowers/specs/mockups/2026-06-29-frontend/` (`studio-full.html`, `gallery-full.html`, `side-panel.html`, `diagnostics-full.html`). These are the pixel reference for the fwr loop.

---

## Verification model (read once)

Two kinds of task, two gates:

- **Logic tasks (2, 3, and the pure helpers in 5/7/8):** classic TDD. Write the failing Vitest test, run it red, implement minimally, run it green, commit. Full test + impl code is in the steps.
- **Visual tasks (4, 5-UI, 6, 7-UI, 9, 10):** the deliverable is "this route matches its mockup and exposes the typed props/behaviors listed." Procedure for each:
  1. Invoke `frontend-design` to build the component(s) to the listed interface + behavior.
  2. `npm run dev` (and a running `variant-server` when live data is needed).
  3. Use `anthropic-skills:fwr` to screenshot the route and compare against the named mockup; iterate until it matches (layout, tokens, density).
  4. Commit.
  The interface contracts + behavior bullets are the acceptance criteria — they are not placeholders.

**Reusable fwr gate (visual tasks reference this):**
```
1. Ensure `npm run dev` (web) is up; for live data also run `variant-server --data-dir <dir>`.
2. Invoke anthropic-skills:fwr → screenshot the route under test at 1440×900.
3. Open the named committed mockup (docs/superpowers/specs/mockups/2026-06-29-frontend/<file>.html) in the same viewport.
4. Compare layout, design tokens (§2), spacing, density. List diffs; fix via frontend-design; re-screenshot until it matches.
```

## Plan convention — why Tasks 4–10 delegate visual build to frontend-design

This plan is executed **subagent-driven with the `frontend-design` skill**, per the project owner's explicit directive ("subagent-driven build using frontend-design and fwr for the screenshot-compare loop"). For the visual tasks the plan therefore specifies, for each component: its **file**, its **typed props/interface**, the **exact data wiring** (which API call / hook / store it consumes — the non-visual logic), its **behaviors**, and the **named mockup** that is the pixel oracle, verified by the fwr loop. It intentionally does **not** transcribe pixel-exact JSX, because (a) the owner directed `frontend-design` to own UI implementation, and (b) the committed mockup is a more precise oracle than prose-described markup, and dictating both would conflict. This is the accepted convention that overrides the skill's default "complete code in every step" for visual components only. **Logic** (API client, formatters, SSE reducer, pure UI helpers) is still built with full test+impl code under strict TDD — see Tasks 2, 3, and the helper steps in 5/7/8.

---

## File Structure (spec §5)

```
web/
  app/{layout.tsx, page.tsx, gallery/page.tsx, diagnostics/page.tsx, globals.css}
  components/nav/{TopNav,StatusStrip}.tsx
  components/studio/{DropZone,FileList,VariantStepper,GenerateButton,AdvancedPanel,ProgressPanel,SourceProgressCard}.tsx
  components/gallery/{GalleryToolbar,SourceGroup,VariantCard}.tsx
  components/variant/{VariantSheet,CompareSlider,ScrubBar,QualityPanel,VariantActions}.tsx
  components/diagnostics/{DiagnosticsList,DiagnosticsRow}.tsx
  components/common/{VideoThumb,Badge,ProgressBar}.tsx
  lib/{types.ts,api.ts,format.ts,progress.ts,useJobProgress.ts,useGallery.ts,useDiagnostics.ts,useJobDetail.ts,runStore.tsx}
  next.config.js  tailwind.config.ts  postcss.config.js  vitest.config.ts  vitest.setup.ts
  package.json  tsconfig.json
```

---

## Task 1: Scaffold app + tokens + dev proxy + proxy/SSE smoke

**Files:**
- Create: `web/` (via create-next-app), `web/next.config.js`, `web/tailwind.config.ts`, `web/app/globals.css`, `web/app/layout.tsx` (minimal), `web/app/page.tsx` (minimal), `web/.env.local.example`
- Create: `web/scripts/sse-smoke.mjs`

**Interfaces:**
- Produces: a themed empty shell on `http://localhost:3000`; `/api/health` reachable through the proxy; the design tokens available as Tailwind colors (`bg-bg`, `text-text`, `text-violet`, etc.).

- [ ] **Step 1: Scaffold**

Run (from `variant-maker/`):
```bash
npx create-next-app@latest web --ts --tailwind --app --eslint --no-src-dir --import-alias "@/*" --use-npm --no-turbopack
```
Accept defaults. Confirm `web/app/` and `web/tailwind.config.ts` exist.

- [ ] **Step 2: Wire the dev proxy**

Create `web/next.config.js`:
```js
/** @type {import('next').NextConfig} */
const target = process.env.API_PROXY_TARGET || "http://localhost:8000";
module.exports = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${target}/api/:path*` }];
  },
};
```
Create `web/.env.local.example`:
```
# Where the FastAPI control plane runs. Used by the dev proxy in next.config.js.
API_PROXY_TARGET=http://localhost:8000
```

- [ ] **Step 3: Tokens into Tailwind**

In `web/tailwind.config.ts`, set the theme colors to the §2 tokens (verbatim):
```ts
import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0a0a0e", panel: "#101018", panel2: "#15151f",
        line: "#23232f", line2: "#2c2c3a",
        text: "#ececf4", muted: "#8a8aa0", muted2: "#62627a",
        violet: "#7c5cff", violetL: "#a78bfa", cyan: "#22d3ee", pink: "#ff4d8d",
        green: "#22c55e", amber: "#f59e0b", red: "#f87171",
      },
      backgroundImage: {
        "cta": "linear-gradient(135deg, #7c5cff, #ff4d8d)",
        "progress": "linear-gradient(90deg, #7c5cff, #22d3ee)",
      },
    },
  },
  plugins: [],
};
export default config;
```
In `web/app/globals.css`, after the Tailwind directives, set the page base:
```css
:root { color-scheme: dark; }
html, body { background:#0a0a0e; color:#ececf4; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
```

- [ ] **Step 4: Minimal shell renders**

Replace `web/app/page.tsx`:
```tsx
export default function Home() {
  return <main className="p-8 text-text">Variant Studio — shell OK</main>;
}
```
Run `npm run dev`; open `http://localhost:3000`. Expected: dark page, "shell OK" in light text.

- [ ] **Step 5: Verify the health proxy (MUST)**

With `npm run dev` running, in another shell start the API and curl through the proxy:
```bash
# from variant-maker/
./.venv/bin/variant-server --data-dir /tmp/vmdata-fe &   # port 8000
curl -s http://localhost:3000/api/health
```
Expected: `{"status":"ok"}` (proxied from :8000 through :3000).

- [ ] **Step 6: SSE streaming smoke through the proxy (SHOULD — the spec §3 risk)**

This proves SSE streams **incrementally** through the Next proxy (not buffered to the end). Needs ffmpeg+libvmaf (same as the engine integration tests). If unavailable in this environment, **log that it is deferred to Task 6** and continue.

Find a tiny fixture:
```bash
./.venv/bin/python -c "import pathlib; print([p.name for p in pathlib.Path('tests/fixtures').glob('*')])"
```
Create `web/scripts/sse-smoke.mjs`:
```js
// Usage: node web/scripts/sse-smoke.mjs <path-to-fixture.mp4>
// Posts a 1-variant job through the proxy, streams events, prints arrival deltas.
import { readFileSync } from "node:fs";
const BASE = "http://localhost:3000";
const file = process.argv[2];
const fd = new FormData();
fd.append("count", "1");
fd.append("files", new Blob([readFileSync(file)], { type: "video/mp4" }), "smoke.mp4");
const created = await (await fetch(`${BASE}/api/jobs`, { method: "POST", body: fd })).json();
console.log("job", created.job_id);
const res = await fetch(`${BASE}/api/jobs/${created.job_id}/events`, { headers: { Accept: "text/event-stream" } });
const reader = res.body.getReader();
const dec = new TextDecoder();
let t0 = Date.now(), seen = 0;
for (;;) {
  const { value, done } = await reader.read();
  if (done) break;
  const chunk = dec.decode(value);
  for (const line of chunk.split("\n")) {
    if (line.startsWith("data:")) {
      seen++;
      console.log(`+${Date.now() - t0}ms`, line.slice(5).trim().slice(0, 80));
      if (line.includes("job-done")) { console.log(`OK: ${seen} events, streamed incrementally`); process.exit(0); }
    }
  }
}
```
Run: `node web/scripts/sse-smoke.mjs tests/fixtures/<fixture>.mp4`
Expected: several `data:` lines with **spread-out** `+Nms` deltas (rendering→checking→done→job-done), not all at `+~Xms` at once. If they all arrive bunched at the very end, the dev rewrite is buffering → switch to **plan B (frontend-only): a Next.js Route Handler** at `web/app/api/jobs/[job_id]/events/route.ts` that `fetch`es the upstream SSE and returns its `ReadableStream` with `Content-Type: text/event-stream` (route handlers stream; no rewrite buffering; **no backend change**). Note the switch for the user — it needs no backend edit.

- [ ] **Step 7: Commit**
```bash
git add web && git commit -m "feat(web): scaffold Next.js app, design tokens, dev proxy + SSE smoke"
```

---

## Task 2: API types, client, and formatters (TDD, Vitest)

**Files:**
- Create: `web/vitest.config.ts`, `web/vitest.setup.ts`, `web/lib/types.ts`, `web/lib/api.ts`, `web/lib/format.ts`
- Test: `web/lib/__tests__/api.test.ts`, `web/lib/__tests__/format.test.ts`
- Modify: `web/package.json` (test script + deps)

**Interfaces:**
- Produces:
  - `lib/types.ts`: `Quality`, `VariantOut`, `SourceOut`, `JobSummary`, `JobDetail`, `CreateJobResponse`, `DiagnosticsItem`, `VariantEvent` (spec §8).
  - `lib/api.ts`: `getHealth()`, `createJob(files: File[], count: number): Promise<CreateJobResponse>`, `getJobs()`, `getJob(id)`, `getGallery()`, `getDiagnostics()`, `regenerate(sourceId: string, n: number): Promise<SourceOut>`, `variantUrl(sourceId, filename)`, `sourceUrl(sourceId)`, `eventsUrl(jobId)`. All use relative `/api`.
  - `lib/format.ts`: `formatDuration(s: number): string`, `vmafPass(v: number): boolean` (≥90), `diagnosticsReason(d: DiagnosticsItem): { title: string; metric: string; corrupt: boolean }`.

- [ ] **Step 1: Add deps + test tooling**
```bash
cd web
npm i swr lucide-react @radix-ui/react-dialog @radix-ui/react-popover @radix-ui/react-dropdown-menu clsx tailwind-merge
npm i -D vitest @testing-library/react @testing-library/jest-dom jsdom @vitejs/plugin-react
```
Add to `web/package.json` scripts: `"test": "vitest run"`, `"test:watch": "vitest"`.

- [ ] **Step 2: Vitest config**

Create `web/vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", setupFiles: ["./vitest.setup.ts"], globals: true },
  resolve: { alias: { "@": resolve(__dirname, ".") } },
});
```
Create `web/vitest.setup.ts`:
```ts
import "@testing-library/jest-dom";
```

- [ ] **Step 3: Write failing `format.test.ts`**
```ts
import { describe, it, expect } from "vitest";
import { formatDuration, vmafPass, diagnosticsReason } from "@/lib/format";

describe("formatDuration", () => {
  it("formats seconds as m:ss", () => {
    expect(formatDuration(18)).toBe("0:18");
    expect(formatDuration(42)).toBe("0:42");
    expect(formatDuration(95)).toBe("1:35");
  });
});

describe("vmafPass", () => {
  it("passes at or above floor 90", () => {
    expect(vmafPass(90)).toBe(true);
    expect(vmafPass(84.2)).toBe(false);
  });
});

describe("diagnosticsReason", () => {
  const q = (over: Partial<any>) => ({ vmaf: 84.2, histogram_ok: true, regen_count: 3, passed: false, spatial_vmaf: null, spatial_ok: null, ...over });
  it("below-floor reason carries the vmaf metric", () => {
    const r = diagnosticsReason({ source_id: "s", index: 19, filename: "v19.mp4", status: "best_effort", quality: q({}) });
    expect(r.corrupt).toBe(false);
    expect(r.metric).toContain("84.2");
    expect(r.metric).toContain("90");
  });
  it("corrupt reason carries the spatial metric", () => {
    const r = diagnosticsReason({ source_id: "s", index: 7, filename: "v07.mp4", status: "corrupt", quality: q({ passed: false, spatial_ok: false, spatial_vmaf: 22.0 }) });
    expect(r.corrupt).toBe(true);
    expect(r.metric).toContain("22");
  });
});
```

- [ ] **Step 4: Run red**

Run: `npm test -- format` — Expected: FAIL (module not found).

- [ ] **Step 5: Implement `types.ts` + `format.ts`**

`web/lib/types.ts`:
```ts
export interface Quality {
  vmaf: number; histogram_ok: boolean; regen_count: number; passed: boolean;
  spatial_vmaf: number | null; spatial_ok: boolean | null;
}
export type Status = "ok" | "best_effort" | "corrupt";
export interface VariantOut { index: number; filename: string; status: Status; quality: Quality; file_url: string; }
export interface SourceOut { source_id: string; filename: string; requested: number; delivered: number; shortfall: number; variants: VariantOut[]; }
export interface JobSummary { job_id: string; count: number; created_utc: string; state: "running" | "done"; source_count: number; }
export interface JobDetail { job_id: string; count: number; created_utc: string; state: string; sources: SourceOut[]; }
export interface CreateJobResponse { job_id: string; sources: SourceOut[]; }
export interface DiagnosticsItem { source_id: string; index: number; filename: string; status: "best_effort" | "corrupt"; quality: Quality; }
export interface VariantEvent {
  source_id: string; index: number;
  state: "rendering" | "checking" | "rerolling" | "done";
  attempt: number; max_attempts: number;
  status: string | null; quality: Quality | null; filename: string | null;
}
export const VMAF_FLOOR = 90;
```
`web/lib/format.ts`:
```ts
import { DiagnosticsItem, VMAF_FLOOR } from "./types";

export function formatDuration(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60).toString().padStart(2, "0");
  return `${m}:${sec}`;
}
export function vmafPass(v: number): boolean { return v >= VMAF_FLOOR; }

export function diagnosticsReason(d: DiagnosticsItem): { title: string; metric: string; corrupt: boolean } {
  if (d.status === "corrupt" || d.quality.spatial_ok === false) {
    const sv = d.quality.spatial_vmaf ?? 0;
    return {
      title: "Neural upscale tore the frame (spatial-corruption guard)",
      metric: `Spatial VMAF ${sv.toFixed(1)} < corruption floor · rejected before delivery`,
      corrupt: true,
    };
  }
  return {
    title: "Quality stayed under the floor after 3 re-rolls",
    metric: `VMAF ${d.quality.vmaf.toFixed(1)} < floor ${VMAF_FLOOR} · histogram ${d.quality.histogram_ok ? "OK" : "fail"}`,
    corrupt: false,
  };
}
```

- [ ] **Step 6: Run green**

Run: `npm test -- format` — Expected: PASS.

- [ ] **Step 7: Write failing `api.test.ts`**
```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import * as api from "@/lib/api";

beforeEach(() => { vi.restoreAllMocks(); });

describe("url builders use relative /api", () => {
  it("variantUrl / sourceUrl / eventsUrl", () => {
    expect(api.variantUrl("s1", "v01.mp4")).toBe("/api/variants/s1/v01.mp4");
    expect(api.sourceUrl("s1")).toBe("/api/sources/s1/source");
    expect(api.eventsUrl("j1")).toBe("/api/jobs/j1/events");
  });
});

describe("createJob posts multipart with files + count", () => {
  it("sends FormData to /api/jobs", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ job_id: "j1", sources: [] }), { status: 201 }));
    const f = new File([new Uint8Array([1, 2])], "a.mp4", { type: "video/mp4" });
    const out = await api.createJob([f], 3);
    expect(out.job_id).toBe("j1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/jobs");
    expect((init as RequestInit).method).toBe("POST");
    expect((init as RequestInit).body).toBeInstanceOf(FormData);
    const body = (init as RequestInit).body as FormData;
    expect(body.get("count")).toBe("3");
    expect(body.getAll("files").length).toBe(1);
  });
});

describe("regenerate posts form n", () => {
  it("sends n to the regenerate route", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ source_id: "s1", filename: "a.mp4", requested: 2, delivered: 2, shortfall: 0, variants: [] }), { status: 200 }));
    await api.regenerate("s1", 2);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/sources/s1/regenerate");
    const body = (init as RequestInit).body as FormData;
    expect(body.get("n")).toBe("2");
  });
});
```

- [ ] **Step 8: Run red**

Run: `npm test -- api` — Expected: FAIL.

- [ ] **Step 9: Implement `api.ts`**
```ts
import { CreateJobResponse, DiagnosticsItem, JobDetail, JobSummary, SourceOut } from "./types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const variantUrl = (sourceId: string, filename: string) => `/api/variants/${sourceId}/${filename}`;
export const sourceUrl = (sourceId: string) => `/api/sources/${sourceId}/source`;
export const eventsUrl = (jobId: string) => `/api/jobs/${jobId}/events`;

export const getHealth = () => fetch("/api/health").then(json<{ status: string }>);
export const getJobs = () => fetch("/api/jobs").then(json<JobSummary[]>);
export const getJob = (id: string) => fetch(`/api/jobs/${id}`).then(json<JobDetail>);
export const getGallery = () => fetch("/api/gallery").then(json<SourceOut[]>);
export const getDiagnostics = () => fetch("/api/diagnostics").then(json<DiagnosticsItem[]>);

export function createJob(files: File[], count: number): Promise<CreateJobResponse> {
  const fd = new FormData();
  fd.append("count", String(count));
  for (const f of files) fd.append("files", f, f.name);
  return fetch("/api/jobs", { method: "POST", body: fd }).then(json<CreateJobResponse>);
}

export function regenerate(sourceId: string, n: number): Promise<SourceOut> {
  const fd = new FormData();
  fd.append("n", String(n));
  return fetch(`/api/sources/${sourceId}/regenerate`, { method: "POST", body: fd }).then(json<SourceOut>);
}
```

- [ ] **Step 10: Run green + commit**

Run: `npm test` — Expected: PASS (format + api).
```bash
git add web && git commit -m "feat(web): typed API client, models, formatters (TDD)"
```

---

## Task 3: SSE progress reducer + useJobProgress hook (TDD, Vitest)

**Files:**
- Create: `web/lib/progress.ts`, `web/lib/useJobProgress.ts`
- Test: `web/lib/__tests__/progress.test.ts`, `web/lib/__tests__/useJobProgress.test.ts`

**Interfaces:**
- Consumes: `VariantEvent`, `Quality`, `variantUrl` (Task 2).
- Produces:
  - `progress.ts`: `SourceProgress`, `RunProgress`, `initRun(sources: {source_id:string; filename:string; requested:number}[]): RunProgress`, `reduceEvent(run: RunProgress, ev: VariantEvent | {state:"job-done"}): RunProgress` (immutable; **idempotent on replayed `done` events** — the backend replays the full log on every (re)connect and `EventSource` auto-reconnects, so a `done` for an `index` already present is a no-op).
  - `useJobProgress.ts`: `useJobProgress(jobId: string | null, sources: {source_id;filename;requested}[]): RunProgress` — opens `EventSource(eventsUrl(jobId))` **only once both `jobId` and `sources` are known** (re-inits when either changes), reduces, closes on `job-done`. (Mounted by `RunProvider` in Task 4 — the app-level SSE owner — not by a page, so the run survives navigation.)

- [ ] **Step 1: Write failing `progress.test.ts`**
```ts
import { describe, it, expect } from "vitest";
import { initRun, reduceEvent } from "@/lib/progress";
import { VariantEvent } from "@/lib/types";

const q = { vmaf: 95, histogram_ok: true, regen_count: 0, passed: true, spatial_vmaf: null, spatial_ok: null };
const ev = (o: Partial<VariantEvent>): VariantEvent =>
  ({ source_id: "s1", index: 1, state: "rendering", attempt: 0, max_attempts: 0, status: null, quality: null, filename: null, ...o });

describe("progress reducer", () => {
  const base = () => initRun([{ source_id: "s1", filename: "a.mp4", requested: 2 }]);

  it("seeds sources with requested and zero counts", () => {
    const r = base();
    expect(r.bySource.s1.requested).toBe(2);
    expect(r.bySource.s1.delivered).toBe(0);
    expect(r.complete).toBe(false);
  });

  it("rendering/checking set inFlight", () => {
    let r = base();
    r = reduceEvent(r, ev({ state: "rendering", index: 1 }));
    expect(r.bySource.s1.inFlight).toEqual({ index: 1, state: "rendering", attempt: 0, max_attempts: 0 });
    r = reduceEvent(r, ev({ state: "checking", index: 1 }));
    expect(r.bySource.s1.inFlight?.state).toBe("checking");
  });

  it("rerolling carries attempt/max", () => {
    let r = base();
    r = reduceEvent(r, ev({ state: "rerolling", index: 1, attempt: 2, max_attempts: 3 }));
    expect(r.bySource.s1.inFlight).toEqual({ index: 1, state: "rerolling", attempt: 2, max_attempts: 3 });
  });

  it("done(ok) appends a tile, bumps delivered+done, builds file_url, clears inFlight", () => {
    let r = base();
    r = reduceEvent(r, ev({ state: "rendering", index: 1 }));
    r = reduceEvent(r, ev({ state: "done", index: 1, status: "ok", quality: q, filename: "v01.mp4" }));
    const s = r.bySource.s1;
    expect(s.delivered).toBe(1);
    expect(s.done).toBe(1);
    expect(s.inFlight).toBeUndefined();
    expect(s.variants[0]).toMatchObject({ index: 1, filename: "v01.mp4", status: "ok", file_url: "/api/variants/s1/v01.mp4" });
  });

  it("done(best_effort) bumps done but not delivered", () => {
    let r = base();
    r = reduceEvent(r, ev({ state: "done", index: 2, status: "best_effort", quality: { ...q, passed: false }, filename: "v02.mp4" }));
    expect(r.bySource.s1.done).toBe(1);
    expect(r.bySource.s1.delivered).toBe(0);
  });

  it("is idempotent on replayed done events (reconnect replays the full log)", () => {
    let r = base();
    const d = ev({ state: "done", index: 1, status: "ok", quality: q, filename: "v01.mp4" });
    r = reduceEvent(r, d);
    r = reduceEvent(r, d); // replayed after an EventSource reconnect
    expect(r.bySource.s1.done).toBe(1);
    expect(r.bySource.s1.delivered).toBe(1);
    expect(r.bySource.s1.variants).toHaveLength(1);
  });

  it("job-done marks complete", () => {
    let r = base();
    r = reduceEvent(r, { state: "job-done" });
    expect(r.complete).toBe(true);
  });

  it("is immutable (returns a new object)", () => {
    const r0 = base();
    const r1 = reduceEvent(r0, ev({ state: "rendering", index: 1 }));
    expect(r1).not.toBe(r0);
    expect(r0.bySource.s1.inFlight).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run red** — `npm test -- progress` → FAIL.

- [ ] **Step 3: Implement `progress.ts`**
```ts
import { VariantEvent, Quality } from "./types";
import { variantUrl } from "./api";

export interface VariantTile { index: number; filename: string; status: string; quality: Quality; file_url: string; }
export interface SourceProgress {
  source_id: string; filename: string; requested: number; delivered: number; done: number;
  inFlight?: { index: number; state: "rendering" | "checking" | "rerolling"; attempt: number; max_attempts: number };
  variants: VariantTile[];
}
export interface RunProgress { bySource: Record<string, SourceProgress>; complete: boolean; }

export function initRun(sources: { source_id: string; filename: string; requested: number }[]): RunProgress {
  const bySource: Record<string, SourceProgress> = {};
  for (const s of sources) bySource[s.source_id] = { ...s, delivered: 0, done: 0, variants: [] };
  return { bySource, complete: false };
}

export function reduceEvent(run: RunProgress, ev: VariantEvent | { state: "job-done" }): RunProgress {
  if (ev.state === "job-done") return { ...run, complete: true };
  const e = ev as VariantEvent;
  const prev = run.bySource[e.source_id];
  if (!prev) return run; // unknown source (shouldn't happen — seeded from CreateJobResponse)
  const next: SourceProgress = { ...prev, variants: prev.variants };
  if (e.state === "rendering" || e.state === "checking" || e.state === "rerolling") {
    next.inFlight = { index: e.index, state: e.state, attempt: e.attempt, max_attempts: e.max_attempts };
  } else if (e.state === "done") {
    if (prev.variants.some((v) => v.index === e.index)) {
      // Idempotent: the backend replays the full event log on every (re)connect and
      // EventSource auto-reconnects on network loss. A replayed `done` must not
      // double-append or double-count — only ensure inFlight is cleared.
      if (prev.inFlight?.index === e.index) next.inFlight = undefined;
    } else {
      next.variants = [...prev.variants, {
        index: e.index, filename: e.filename!, status: e.status!, quality: e.quality!,
        file_url: variantUrl(e.source_id, e.filename!),
      }];
      next.done = prev.done + 1;
      if (e.status === "ok") next.delivered = prev.delivered + 1;
      if (prev.inFlight?.index === e.index) next.inFlight = undefined;
    }
  }
  return { ...run, bySource: { ...run.bySource, [e.source_id]: next } };
}
```

- [ ] **Step 4: Run green** — `npm test -- progress` → PASS.

- [ ] **Step 5: Write failing `useJobProgress.test.ts`** (mock EventSource)
```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useJobProgress } from "@/lib/useJobProgress";

class MockES {
  static last: MockES | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  closed = false;
  constructor(public url: string) { MockES.last = this; }
  close() { this.closed = true; }
  emit(obj: unknown) { this.onmessage?.({ data: JSON.stringify(obj) }); }
}
beforeEach(() => { (globalThis as any).EventSource = MockES as any; MockES.last = null; });

describe("useJobProgress", () => {
  const sources = [{ source_id: "s1", filename: "a.mp4", requested: 1 }];
  it("reduces streamed events and closes on job-done", () => {
    const { result } = renderHook(() => useJobProgress("j1", sources));
    expect(MockES.last?.url).toBe("/api/jobs/j1/events");
    act(() => { MockES.last!.emit({ source_id: "s1", index: 1, state: "rendering", attempt: 0, max_attempts: 0, status: null, quality: null, filename: null }); });
    expect(result.current.bySource.s1.inFlight?.state).toBe("rendering");
    act(() => { MockES.last!.emit({ source_id: "s1", index: 1, state: "done", attempt: 0, max_attempts: 0, status: "ok", quality: { vmaf: 95, histogram_ok: true, regen_count: 0, passed: true, spatial_vmaf: null, spatial_ok: null }, filename: "v01.mp4" }); });
    expect(result.current.bySource.s1.delivered).toBe(1);
    act(() => { MockES.last!.emit({ state: "job-done" }); });
    expect(result.current.complete).toBe(true);
    expect(MockES.last!.closed).toBe(true);
  });
  it("does nothing when jobId is null", () => {
    renderHook(() => useJobProgress(null, sources));
    expect(MockES.last).toBeNull();
  });
  it("waits until sources are known before opening", () => {
    renderHook(() => useJobProgress("j1", []));
    expect(MockES.last).toBeNull();
  });
});
```

- [ ] **Step 6: Run red** — `npm test -- useJobProgress` → FAIL.

- [ ] **Step 7: Implement `useJobProgress.ts`**
```ts
"use client";
import { useEffect, useRef, useState } from "react";
import { eventsUrl } from "./api";
import { initRun, reduceEvent, RunProgress } from "./progress";

export function useJobProgress(
  jobId: string | null,
  sources: { source_id: string; filename: string; requested: number }[],
): RunProgress {
  const [run, setRun] = useState<RunProgress>(() => initRun(sources));
  const runRef = useRef(run);
  runRef.current = run;
  const sourcesKey = sources.map((s) => s.source_id).join(",");
  useEffect(() => {
    if (!jobId || sources.length === 0) return; // wait for sources (fresh start: immediate; reload: after job detail seeds them)
    const fresh = initRun(sources);
    runRef.current = fresh;
    setRun(fresh);
    const es = new EventSource(eventsUrl(jobId));
    es.onmessage = (e) => {
      const ev = JSON.parse(e.data);
      const next = reduceEvent(runRef.current, ev);
      runRef.current = next;
      setRun(next);
      if (ev.state === "job-done") es.close();
    };
    return () => es.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, sourcesKey]);
  return run;
}
```

- [ ] **Step 8: Run green + commit**

Run: `npm test` — Expected: PASS (all suites).
```bash
git add web && git commit -m "feat(web): SSE progress reducer + useJobProgress hook (TDD)"
```

---

## Task 4: App shell — TopNav + StatusStrip + routes (visual)

**Files:**
- Create: `web/components/nav/TopNav.tsx`, `web/components/nav/StatusStrip.tsx`, `web/lib/runStore.tsx`
- Modify: `web/app/layout.tsx`; Create stubs `web/app/gallery/page.tsx`, `web/app/diagnostics/page.tsx`

**Interfaces:**
- Consumes: `getHealth`, `getJob` (Task 2), `useJobProgress` (Task 3).
- Produces:
  - `<TopNav/>` — **client component** (`"use client"`); logo + nav links (`/`, `/gallery`, `/diagnostics`) with the active link derived from `usePathname()`; `<StatusStrip/>` right-aligned. Rendered **once** in `app/layout.tsx`; pages never render their own TopNav (avoids duplicate bars / an unimplementable per-page `active` prop).
  - `<StatusStrip/>` — polls `getHealth` (SWR, 10s), shows "Engine ready" green pill (or "Engine offline" red) + "Local · CPU fast" pill.
  - `runStore.tsx`: `RunProvider` is the **app-level SSE owner** — mounted in `app/layout.tsx` above all pages, so the run keeps streaming across navigation (spec §6). It holds `jobId` + `sources`, runs `progress = useJobProgress(jobId, sources)` (Task 3) **at the provider level**, and exposes `useRun()` → `{ jobId, sources, progress: RunProgress, complete: boolean, start(resp: CreateJobResponse), clear() }` where `complete = progress.complete`. Behavior: `start(resp)` sets `jobId` (+`sessionStorage("vm.job")`) and `sources` from `resp.sources`; on mount it **hydrates `jobId` from sessionStorage** and, if `sources` is empty, fetches `getJob(jobId)` **once** to seed `sources` (filename + requested) before the stream opens (reattach after a hard reload); `clear()` drops state + sessionStorage. Because the stream lives here, **both Studio's ProgressPanel and Gallery just read `useRun()`** — neither owns the EventSource, so Gallery sees `complete` even when Studio is unmounted.

- [ ] **Step 1: Build to interface** — invoke `frontend-design` for `TopNav` (client, `usePathname`) + `StatusStrip` against the interfaces above and the top bar in `studio-full.html`. In `app/layout.tsx` wrap `{children}` with `RunProvider` and render a single `<TopNav/>` above them. Create `app/gallery/page.tsx` and `app/diagnostics/page.tsx` as just an empty `<main className="p-6">` with the page `<h1>` — TopNav is inherited from the layout (real content lands in Tasks 7/10).
- [ ] **Step 2: Behavior** — StatusStrip green "Engine ready" pill when `/api/health` ok (red "Engine offline" otherwise); the nav link matching the current `usePathname()` is highlighted; `useRun()` exposes `{jobId, sources, progress, complete}` from the app-level stream, survives client navigation, and persists `jobId` to `sessionStorage` for hard-reload reattach.
- [ ] **Step 3: Visual gate** — run the **Reusable fwr gate** against `/` with mockup `studio-full.html` (top bar region). (`variant-server` running so the health pill is green.)
- [ ] **Step 4: Commit** — `git add web && git commit -m "feat(web): app shell — TopNav, StatusStrip, run store, routes"`

---

## Task 5: Studio cockpit — inputs + Generate (mixed: TDD helpers + visual)

**Files:**
- Create: `web/components/studio/{DropZone,FileList,VariantStepper,GenerateButton,AdvancedPanel}.tsx`, `web/lib/files.ts`
- Test: `web/lib/__tests__/files.test.ts`
- Modify: `web/app/page.tsx` (Studio left column)

**Interfaces:**
- Consumes: `createJob` (Task 2), `useRun` (Task 4).
- Produces:
  - `lib/files.ts`: `accepts(file: File): boolean` (video/* by mime or .mp4/.mov), `totalVariants(fileCount: number, perVideo: number): number`, `readDurations(files: File[]): Promise<number[]>` (uses a temporary `<video>`’s `loadedmetadata`).
  - `<DropZone onFiles>`, `<FileList files durations onRemove>`, `<VariantStepper value onChange min=1>`, `<GenerateButton fileCount perVideo onClick>`, `<AdvancedPanel/>` (collapsed; "Output: Vertical 1080×1920").
  - Studio left column: select files → list with durations → set count → Generate calls `createJob` then `useRun().start(resp)`.

- [ ] **Step 1: Write failing `files.test.ts`**
```ts
import { describe, it, expect } from "vitest";
import { accepts, totalVariants } from "@/lib/files";
describe("files helpers", () => {
  it("accepts video files", () => {
    expect(accepts(new File([], "a.mp4", { type: "video/mp4" }))).toBe(true);
    expect(accepts(new File([], "a.mov", { type: "" }))).toBe(true);
    expect(accepts(new File([], "a.txt", { type: "text/plain" }))).toBe(false);
  });
  it("totalVariants multiplies per-video by file count", () => {
    expect(totalVariants(2, 20)).toBe(40);
    expect(totalVariants(0, 20)).toBe(0);
  });
});
```
- [ ] **Step 2: Run red** — `npm test -- files` → FAIL.
- [ ] **Step 3: Implement `lib/files.ts`**
```ts
export function accepts(file: File): boolean {
  if (file.type.startsWith("video/")) return true;
  return /\.(mp4|mov|m4v|webm)$/i.test(file.name);
}
export function totalVariants(fileCount: number, perVideo: number): number { return fileCount * perVideo; }
export function readDurations(files: File[]): Promise<number[]> {
  return Promise.all(files.map(f => new Promise<number>((resolve) => {
    const v = document.createElement("video");
    v.preload = "metadata";
    v.onloadedmetadata = () => { URL.revokeObjectURL(v.src); resolve(v.duration || 0); };
    v.onerror = () => resolve(0);
    v.src = URL.createObjectURL(f);
  })));
}
```
- [ ] **Step 4: Run green** — `npm test -- files` → PASS.
- [ ] **Step 5: Build the cockpit UI** — invoke `frontend-design` for DropZone/FileList/VariantStepper/GenerateButton/AdvancedPanel and assemble the Studio left column per `studio-full.html` (left side). Wire Generate → `createJob(files, perVideo)` → `useRun().start(resp)`.
- [ ] **Step 6: Visual gate** — fwr screenshot `/` left column vs `studio-full.html`; iterate. Behavior: drop 2 files → list shows durations → stepper shows "2 clips → 40 total" → Generate posts (verify against running `variant-server`: a `job_id` returns).
- [ ] **Step 7: Commit** — `git add web && git commit -m "feat(web): Studio cockpit inputs + Generate (files helpers TDD)"`

---

## Task 6: Studio live progress panel (visual + live integration)

**Files:**
- Create: `web/components/studio/{ProgressPanel,SourceProgressCard}.tsx`, `web/components/common/{ProgressBar,Badge,VideoThumb}.tsx`
- Modify: `web/app/page.tsx` (right column)

**Interfaces:**
- Consumes: `useRun` (Task 4) → its `{ jobId, progress, complete }`, `SourceProgress` (Task 3).
- Produces:
  - `<ProgressPanel/>` — reads `useRun()`; if `jobId`, renders one `<SourceProgressCard source={progress.bySource[id]}/>` for each source in `progress.bySource`; empty state before a run. **It owns no EventSource** — the stream and the reattach-after-reload logic live in `RunProvider` (Task 4); this panel only renders `progress`.
  - `<SourceProgressCard source: SourceProgress>` — thumb, name, `delivered/requested`, `<ProgressBar value={done/requested}/>`, live status line (cyan `● vNN rendering…`, amber `↻ vNN re-rolling a/max`), streamed `<VideoThumb>` strip (9:16, VMAF badge), and a "<N> ready" cue.
  - `<VideoThumb src poster? badge?>` — `<video preload="metadata" muted playsInline>`, hover plays/loops, mouse-out pauses+resets.

**Live data-flow reality (locked API):** per-variant tiles appear **here in Studio** as `done` events arrive over SSE — this is the live per-variant view. The **Gallery** page reads `/api/gallery`, which the backend populates from `JobSource.variants` **only after a source's whole run completes** (see `jobs.py`), so Gallery shows a source once it finishes, not per-variant mid-run. Do **not** claim per-variant Gallery streaming. (Task 7 revalidates Gallery when a run completes so finished sources appear without a manual refresh.)

- [ ] **Step 1: Build to interface** — `frontend-design` for ProgressPanel/SourceProgressCard/ProgressBar/Badge/VideoThumb; assemble Studio right column.
- [ ] **Step 2: Behavior** — status line shows live rendering + visible re-rolls; bar = `done/requested`; tiles appear as `done` events arrive; empty state before a run.
- [ ] **Step 3: Visual gate** — fwr screenshot `/` (full, mid-run) vs `studio-full.html`; iterate.
- [ ] **Step 4: LIVE integration gate** — start `variant-server` with a real tiny clip; in the browser drop it, count=2, Generate; confirm: live status updates, re-roll line appears if any, `done` tiles stream in, completes. **Hard-reload mid-run → progress re-attaches** (RunProvider hydrates jobId from sessionStorage, re-seeds sources via `getJob`, the SSE replays the log). This is the spec §3 SSE-through-proxy confirmation (resolve the Task 1 deferral here; if buffering is seen, switch to the **frontend-only Next.js Route Handler** — plan B, no backend change).
- [ ] **Step 5: Commit** — `git add web && git commit -m "feat(web): Studio live progress panel + video thumbnail primitive"`

---

## Task 7: Gallery — toolbar, groups, cards, regenerate (mixed)

**Files:**
- Create: `web/components/gallery/{GalleryToolbar,SourceGroup,VariantCard}.tsx`, `web/lib/useGallery.ts`, `web/lib/gallery.ts`
- Test: `web/lib/__tests__/gallery.test.ts`
- Modify: `web/app/gallery/page.tsx`

**Interfaces:**
- Consumes: `getGallery`, `regenerate` (Task 2), `VideoThumb`/`Badge` (Task 6).
- Produces:
  - `lib/gallery.ts`: `filterSources(sources, mode: "all" | "shortfall")`, `sortSources(sources, by: "newest")` (pure).
  - `useGallery()` — SWR over `getGallery` (`revalidateOnFocus`), exposes `mutate`. The Gallery page also watches `useRun()`; when the active run flips to `complete`, it calls `mutate()` so newly-finished sources appear without a manual refresh (the API only exposes a source after its run completes — see Task 6 data-flow note).
  - `<GalleryToolbar count filterMode onFilter sort onSort/>`, `<SourceGroup source onOpenVariant onRegenerate/>` (collapsible; header with `delivered/requested` colored green/amber; **shortfall bar + Regenerate only when `shortfall>0`**; 8-across grid of `<VariantCard>`), `<VariantCard variant onOpen/>` (9:16 VideoThumb + VMAF badge; **spatial tick shown only when `quality.spatial_ok === true`** — the default Tier-1 fast tier has no neural pass so `spatial_ok`/`spatial_vmaf` are `null` → VMAF badge only).
  - Click a card → navigate `/gallery?v=<source_id>:<index>` (opens sheet in Task 9).

- [ ] **Step 1: Write failing `gallery.test.ts`**
```ts
import { describe, it, expect } from "vitest";
import { filterSources, sortSources } from "@/lib/gallery";
const mk = (id: string, shortfall: number) => ({ source_id: id, filename: id, requested: 5, delivered: 5 - shortfall, shortfall, variants: [] });
describe("gallery helpers", () => {
  it("filter shortfall keeps only under-delivered", () => {
    const all = [mk("a", 0), mk("b", 2)];
    expect(filterSources(all, "shortfall").map(s => s.source_id)).toEqual(["b"]);
    expect(filterSources(all, "all").length).toBe(2);
  });
  it("sort newest reverses insertion order", () => {
    const all = [mk("a", 0), mk("b", 0)];
    expect(sortSources(all, "newest").map(s => s.source_id)).toEqual(["b", "a"]);
  });
});
```
- [ ] **Step 2: Run red** — `npm test -- gallery` → FAIL.
- [ ] **Step 3: Implement `lib/gallery.ts`**
```ts
import { SourceOut } from "./types";
export function filterSources(sources: SourceOut[], mode: "all" | "shortfall"): SourceOut[] {
  return mode === "shortfall" ? sources.filter(s => s.shortfall > 0) : sources;
}
export function sortSources(sources: SourceOut[], by: "newest"): SourceOut[] {
  return by === "newest" ? [...sources].reverse() : sources;
}
```
- [ ] **Step 4: Run green** — `npm test -- gallery` → PASS.
- [ ] **Step 5: Build Gallery UI** — `useGallery` (SWR) + `frontend-design` for GalleryToolbar/SourceGroup/VariantCard; assemble `/gallery`. The group's shortfall Regenerate calls `regenerate(source.source_id, source.shortfall)` then `mutate()`.
- [ ] **Step 6: Visual gate** — fwr screenshot `/gallery` vs `gallery-full.html` (one full group + one shortfall group). Iterate. Verify shortfall bar/Regenerate hidden on full delivery, shown on shortfall.
- [ ] **Step 7: Commit** — `git add web && git commit -m "feat(web): Gallery — toolbar, source groups, variant cards, regenerate"`

---

## Task 8: Media primitives — CompareSlider + ScrubBar (mixed)

**Files:**
- Create: `web/components/variant/{CompareSlider,ScrubBar}.tsx`, `web/lib/media.ts`
- Test: `web/lib/__tests__/media.test.ts`

**Interfaces:**
- Produces:
  - `lib/media.ts`: `clipInset(pct: number): string` → `inset(0 ${100-pct}% 0 0)`; `clampTime(t: number, duration: number): number` (0..duration).
  - `<CompareSlider beforeSrc afterSrc/>` — two stacked `<video>` (after = bottom, before = top clipped by `clipInset`), draggable handle, SOURCE/VARIANT labels.
  - `<ScrubBar videos: RefObject<HTMLVideoElement>[] /> ` — play/pause toggles all; a track sets `currentTime` on each via `clampTime(t, video.duration)`; shows `m:ss / m:ss`.

- [ ] **Step 1: Write failing `media.test.ts`**
```ts
import { describe, it, expect } from "vitest";
import { clipInset, clampTime } from "@/lib/media";
describe("media helpers", () => {
  it("clipInset maps percent to inset", () => {
    expect(clipInset(54)).toBe("inset(0 46% 0 0)");
    expect(clipInset(0)).toBe("inset(0 100% 0 0)");
  });
  it("clampTime clamps to [0,duration]", () => {
    expect(clampTime(-1, 10)).toBe(0);
    expect(clampTime(5, 10)).toBe(5);
    expect(clampTime(99, 10)).toBe(10);
    expect(clampTime(5, 0)).toBe(0);
  });
});
```
- [ ] **Step 2: Run red** — `npm test -- media` → FAIL.
- [ ] **Step 3: Implement `lib/media.ts`**
```ts
export function clipInset(pct: number): string { return `inset(0 ${100 - pct}% 0 0)`; }
export function clampTime(t: number, duration: number): number {
  if (!duration || duration < 0) return 0;
  return Math.min(Math.max(0, t), duration);
}
```
- [ ] **Step 4: Run green** — `npm test -- media` → PASS.
- [ ] **Step 5: Build the components** — `frontend-design` for CompareSlider + ScrubBar using the helpers; both videos share the scrub time (clamped per video so a speed-shifted variant doesn’t overrun).
- [ ] **Step 6: Visual gate** — fwr screenshot the compare area vs the `.compare` block in `side-panel.html` (handle, SOURCE/VARIANT tags, scrub). Iterate. (Built standalone here; mounted in Task 9.)
- [ ] **Step 7: Commit** — `git add web && git commit -m "feat(web): before/after CompareSlider + ScrubBar primitives (helpers TDD)"`

---

## Task 9: Variant side-panel — Sheet + Quality + Actions (visual, URL-driven)

**Files:**
- Create: `web/components/variant/{VariantSheet,QualityPanel,VariantActions}.tsx`
- Modify: `web/app/gallery/page.tsx` (open sheet from `?v=` param)

**Interfaces:**
- Consumes: `CompareSlider`/`ScrubBar` (Task 8), `getGallery`/`useGallery` (Task 7), `regenerate`, `sourceUrl`/`variantUrl` (Task 2).
- Produces:
  - `<VariantSheet sourceId: string, variants: VariantOut[], index: number, onClose, onNav(delta)>` — Radix Dialog/Sheet from the right; header `source · vNN`, "variant k of `variants.length`", filename, prev/next (`onNav(±1)` clamped within `variants`), close; body = CompareSlider(beforeSrc=`sourceUrl(sourceId)`, afterSrc=`variants[index].file_url`) + ScrubBar + `<QualityPanel>` + `<VariantActions>`. Keyboard `←/→`/`Esc`. (Taking `variants[]` rather than a `SourceOut` lets Diagnostics open a **single-variant** sheet in Task 10.)
  - `<QualityPanel quality: Quality>` — VMAF (green if `vmafPass`), Spatial guard (when `spatial_ok===null` show "—/n-a"; else ✓/✗ from `spatial_ok` with `spatial_vmaf`), Histogram (`histogram_ok`), Re-rolls (`regen_count`/3), and a **locked/greyed Similarity** row (`— %`) + park note (spec §9.3).
  - `<VariantActions variant: VariantOut, onRegenerate>` — Download (`<a href={file_url} download>`), **Regenerate this one** (the sheet wires `onRegenerate` to `regenerate(sourceId, 1)` then revalidates the gallery), View manifest entry (renders `VariantOut` JSON in a small disclosure). (No Reveal in Finder — deferred, spec §9.2.)
  - `/gallery?v=<sid>:<idx>` opens the sheet over the (still-mounted) grid; closing clears the param.

- [ ] **Step 1: Build to interface** — `frontend-design` for VariantSheet/QualityPanel/VariantActions; wire `?v=` parsing in the gallery page; reuse Task 8 primitives.
- [ ] **Step 2: Behavior** — prev/next steps within the group without closing; greyed Similarity present; Download saves the file; **Regenerate calls `regenerate(sourceId, 1)`** + `mutate`; manifest disclosure shows the JSON.
- [ ] **Step 3: Visual gate** — fwr screenshot `/gallery?v=<sid>:<idx>` vs `side-panel.html` (dimmed grid behind, panel docked right). Iterate.
- [ ] **Step 4: Commit** — `git add web && git commit -m "feat(web): variant detail side-panel — compare, quality, actions"`

---

## Task 10: Diagnostics page (visual + SWR)

**Files:**
- Create: `web/components/diagnostics/{DiagnosticsList,DiagnosticsRow}.tsx`, `web/lib/useDiagnostics.ts`
- Modify: `web/app/diagnostics/page.tsx`

**Interfaces:**
- Consumes: `getDiagnostics` (Task 2), `diagnosticsReason` (Task 2), `regenerate` (Task 2), `VariantSheet` (Task 9, for Inspect).
- Produces:
  - `useDiagnostics()` — SWR over `getDiagnostics`.
  - `<DiagnosticsList items: DiagnosticsItem[]>` — summary chips (counts of below-floor vs corrupt), grouped by `source_id`; empty state "Nothing failed — all variants delivered."
  - `<DiagnosticsRow item>` — index, status badge (amber BELOW FLOOR / red CORRUPT), `diagnosticsReason(item)` title + metric, `↻ 3/3` (from `regen_count`), actions: **Inspect** (enabled only for `best_effort`; builds a one-element `VariantOut[]` — `{ index, filename, status, quality, file_url: variantUrl(item.source_id, item.filename) }` — and opens `<VariantSheet sourceId={item.source_id} variants={[v]} index={0}/>` from Task 9), Manifest, Regenerate (`regenerate(item.source_id, 1)` then revalidate diagnostics + gallery).

- [ ] **Step 1: Build to interface** — `useDiagnostics` + `frontend-design` for DiagnosticsList/DiagnosticsRow; assemble `/diagnostics`.
- [ ] **Step 2: Behavior** — reasons + metrics from `diagnosticsReason`; Inspect disabled for `corrupt`; chips count correctly; empty state when none.
- [ ] **Step 3: Visual gate** — fwr screenshot `/diagnostics` vs `diagnostics-full.html`. Iterate.
- [ ] **Step 4: Commit** — `git add web && git commit -m "feat(web): Diagnostics page — grouped failures with reasons"`

---

## Task 11: End-to-end verification + run docs

**Files:**
- Create: `web/README.md`, `variant-maker/dev.sh` (convenience: run API + web together)

**Interfaces:** none (integration + docs).

- [ ] **Step 1: Convenience runner**

Create `variant-maker/dev.sh`:
```bash
#!/usr/bin/env bash
# Run the control plane (API + web) for local development.
set -euo pipefail
DATA_DIR="${1:-./.vmdata}"
./.venv/bin/variant-server --data-dir "$DATA_DIR" &
API=$!
trap 'kill $API 2>/dev/null || true' EXIT
( cd web && npm run dev )
```
`chmod +x variant-maker/dev.sh`.

- [ ] **Step 2: Full manual E2E (real engine)**

Start `./dev.sh` (needs ffmpeg+libvmaf). In the browser:
1. Studio: drop 1–2 short clips, set count (e.g. 3), Generate. Watch live progress (status line, any re-rolls, tiles streaming, completion). Reload mid-run → progress re-attaches.
2. Gallery: groups appear; full vs shortfall rendering correct; cards play on hover.
3. Side-panel: open a variant; before/after compare drags; scrub plays both; quality reads from manifest; greyed Similarity present; prev/next works; Download saves the mp4.
4. Shortfall (if any): Regenerate adds variants; counts update.
5. Diagnostics: any `best_effort`/`corrupt` listed with correct reasons; Inspect works for best_effort.

Record results (pass/fail per screen) in the commit message.

- [ ] **Step 3: README**

Create `web/README.md` documenting: prereqs (Node ≥18.18, an ffmpeg+libvmaf build for the engine), `npm install`, running the API (`variant-server --data-dir <dir>`) + `npm run dev` (or `./dev.sh`), the proxy env (`API_PROXY_TARGET`), `npm test`, and the Stage-2 note (swap `API_PROXY_TARGET` to the deployed API to port to Vercel).

- [ ] **Step 4: Full unit suite green**

Run (from `web/`): `npm test` — Expected: PASS (format, api, progress, useJobProgress, files, gallery, media). Run `npm run build` — Expected: production build succeeds.

- [ ] **Step 5: Commit**
```bash
git add web/README.md dev.sh && git commit -m "test(web): end-to-end verification + local run docs"
```

---

## Self-Review

**1. Spec coverage** (spec → task):
- Visual system/tokens → Task 1 (tokens), enforced in every visual task's fwr gate.
- No-rewrite same-origin proxy → Task 1; SSE-through-proxy risk validated Task 1 (smoke) + Task 6 (live).
- API client/types for every endpoint (§8) → Task 2.
- SSE reduction, re-rolls visible, run survives navigation (§6) → Task 3 (reducer+hook, replay-idempotent), Task 4 (RunProvider = app-level SSE owner, exposes `progress`/`complete`, reattach), Task 6 (panel renders `useRun().progress`), Task 7 (Gallery revalidates on `complete`).
- Inline video + posters + compare slider (§7) → Task 6 (VideoThumb), Task 8 (CompareSlider/ScrubBar).
- Studio (§9.1) → Tasks 5, 6. Gallery (§9.2) → Task 7. Side-panel (§9.3) → Tasks 8, 9. Diagnostics (§9.4) → Task 10.
- Reveal-deferred / manifest-scoped / Similarity-greyed (§9.2/§9.3) → Tasks 9, 10 (explicit in interfaces).
- Run model / Vercel port note (§3, §13) → Task 11.

**2. Placeholder scan:** Logic tasks contain full test + impl code. Visual tasks carry typed interfaces + behavior bullets + a named mockup oracle + the fwr loop — these are concrete acceptance criteria, not "TBD". No "add error handling"/"similar to" placeholders.

**3. Type consistency:** `Quality`/`VariantEvent`/`SourceOut` shapes match the backend (`events.py`, `models.py`) and are reused verbatim across `progress.ts`, `api.ts`, components. `initRun`/`reduceEvent`/`useJobProgress` signatures consistent Task 3 → 4 (RunProvider owns the stream; ProgressPanel and Gallery read `useRun()`). `variantUrl`/`sourceUrl`/`eventsUrl` defined Task 2, used in Tasks 3/6/9/10. `filterSources`/`sortSources` defined+used Task 7. `clipInset`/`clampTime` defined Task 8, used Tasks 8/9.

**Open note (not a blocker):** Tasks 4–10 mix true unit gates (where logic exists) with the fwr visual gate. If the executing agent lacks a working Puppeteer/fwr setup, the fallback gate is a manual screenshot diff against the named mockup — the interface contracts still fully specify behavior.

---

## Execution Handoff

(filled in after user review)
