import { createStillUrl } from "./createApi";
import { CreateEvent, CreateJobDetail, CreatePhase, CreateStillOut } from "./createTypes";

export interface CreateStillTile {
  index: number;
  filename: string;
  file_url: string;
  status: "ok" | "failed";
}

export interface CreateRunProgress {
  phase: CreatePhase;
  message: string | null;
  stillsTotal: number;
  stills: CreateStillTile[];
  complete: boolean;
  failed: boolean;
  error: string | null;
}

export function initCreateRun(count: number): CreateRunProgress {
  return {
    phase: "queued",
    message: null,
    stillsTotal: count,
    stills: [],
    complete: false,
    failed: false,
    error: null,
  };
}

function upsertStill(
  stills: CreateStillTile[],
  tile: CreateStillTile,
): CreateStillTile[] {
  const existing = stills.find((s) => s.index === tile.index);
  if (existing) {
    return stills.map((s) => (s.index === tile.index ? { ...s, ...tile } : s));
  }
  return [...stills, tile].sort((a, b) => a.index - b.index);
}

/** Map backend runner event states onto UI CreatePhase. */
function toPhase(state: CreateEvent["state"]): CreatePhase | null {
  switch (state) {
    case "queued":
    case "directing":
    case "generating":
    case "saving":
    case "done":
    case "failed":
      return state;
    case "expanding":
    case "expanded":
      return "directing";
    case "handoff":
      return "saving";
    case "error":
      return "failed";
    case "job-done":
      return "done";
    case "still-done":
      return null;
    default:
      return null;
  }
}

export function reduceCreateEvent(
  run: CreateRunProgress,
  ev: CreateEvent,
): CreateRunProgress {
  if (ev.state === "job-done") {
    return {
      ...run,
      phase: "done",
      complete: true,
      failed: false,
      message: ev.message ?? run.message,
    };
  }

  if (ev.state === "failed" || ev.state === "error") {
    return {
      ...run,
      phase: "failed",
      complete: true,
      failed: true,
      error: ev.error ?? ev.message ?? run.error ?? "Create job failed",
      message: ev.message ?? run.message,
    };
  }

  // Backend emits per-still completion as state:"done" + filename; frontend also accepts still-done.
  const isStillDone =
    ev.state === "still-done" || (ev.state === "done" && !!ev.filename);
  if (isStillDone) {
    if (ev.index == null || !ev.filename) return run;
    const tile: CreateStillTile = {
      index: ev.index,
      filename: ev.filename,
      file_url: ev.file_url || "",
      status: ev.status === "failed" ? "failed" : "ok",
    };
    const stills = upsertStill(run.stills, tile);
    return {
      ...run,
      phase: "generating",
      stills,
      stillsTotal: ev.stills_total ?? run.stillsTotal,
      message: ev.message ?? run.message,
    };
  }

  const phase = toPhase(ev.state);
  if (!phase) return run;

  return {
    ...run,
    phase,
    message: ev.message ?? run.message,
    stillsTotal: ev.stills_total ?? run.stillsTotal,
    complete: phase === "done",
    failed: false,
  };
}

/** Merge a polled job detail into progress (poll fallback when SSE is buffered). */
export function applyCreateJobDetail(
  run: CreateRunProgress,
  detail: CreateJobDetail,
): CreateRunProgress {
  let next = run;
  for (const s of detail.stills) {
    next = reduceCreateEvent(next, stillToEvent(detail.job_id, s));
  }
  next = {
    ...next,
    phase: detail.phase,
    message: detail.message ?? next.message,
    stillsTotal: detail.count,
    error: detail.error,
  };
  if (detail.error || detail.phase === "failed" || detail.state === "failed") {
    next = reduceCreateEvent(next, {
      state: "failed",
      message: detail.error ?? detail.message,
      error: detail.error,
    });
  } else if (detail.state === "done" || detail.phase === "done") {
    next = reduceCreateEvent(next, { state: "job-done", message: detail.message });
  }
  return next;
}

function stillToEvent(jobId: string, s: CreateStillOut): CreateEvent {
  return {
    state: "still-done",
    index: s.index,
    filename: s.filename,
    file_url: s.file_url || createStillUrl(jobId, s.filename),
    status: s.status,
  };
}

export function phaseLabel(phase: CreatePhase): string {
  switch (phase) {
    case "queued":
      return "Queued…";
    case "directing":
      return "Expanding brief…";
    case "generating":
      return "Generating stills…";
    case "saving":
      return "Saving…";
    case "done":
      return "Complete";
    case "failed":
      return "Failed";
  }
}
