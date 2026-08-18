import { VariantEvent, Quality, PlatformResult } from "./types";
import { variantUrl } from "./api";

export interface VariantTile {
  index: number; filename: string; status: string; quality: Quality; file_url: string;
  uniqueness?: number | null; uniqueness_status?: string | null;
  uniqueness_target?: number | null; escalated?: boolean;
  platform_result?: PlatformResult | null;
}
export interface SourceProgress {
  source_id: string; filename: string; requested: number; delivered: number; done: number;
  inFlight?: {
    index: number;
    state: "rendering" | "checking" | "rerolling" | "uniqueness" | "escalating";
    attempt: number; max_attempts: number;
  };
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
  if (
    e.state === "rendering" || e.state === "checking" || e.state === "rerolling" ||
    e.state === "uniqueness" || e.state === "escalating"
  ) {
    next.inFlight = { index: e.index, state: e.state, attempt: e.attempt, max_attempts: e.max_attempts };
  } else if (e.state === "done") {
    const existing = prev.variants.find((v) => v.index === e.index);
    if (existing) {
      // Idempotent: the backend replays the full event log on every (re)connect and
      // EventSource auto-reconnects on network loss. A replayed `done` must not
      // double-append or double-count — only ensure inFlight is cleared.
      // A later polled `done` (with uniqueness/escalated/platform_result) can still
      // enrich a tile that first arrived via a plain SSE `done`.
      next.variants = prev.variants.map((v) =>
        v.index === e.index
          ? {
              ...v,
              uniqueness: e.uniqueness ?? v.uniqueness,
              uniqueness_status: e.uniqueness_status ?? v.uniqueness_status,
              uniqueness_target: e.uniqueness_target ?? v.uniqueness_target,
              escalated: e.escalated ?? v.escalated,
              platform_result: e.platform_result ?? v.platform_result,
            }
          : v,
      );
      if (prev.inFlight?.index === e.index) next.inFlight = undefined;
    } else {
      next.variants = [...prev.variants, {
        index: e.index, filename: e.filename!, status: e.status!, quality: e.quality!,
        file_url: variantUrl(e.source_id, e.filename!),
        uniqueness: e.uniqueness ?? null,
        uniqueness_status: e.uniqueness_status ?? null,
        uniqueness_target: e.uniqueness_target ?? null,
        escalated: e.escalated ?? false,
        platform_result: e.platform_result ?? null,
      }];
      next.done = prev.done + 1;
      if (e.status === "ok") next.delivered = prev.delivered + 1;
      if (prev.inFlight?.index === e.index) next.inFlight = undefined;
    }
  }
  return { ...run, bySource: { ...run.bySource, [e.source_id]: next } };
}
