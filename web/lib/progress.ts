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
