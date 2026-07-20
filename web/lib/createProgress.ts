import { createHandoffUrl, createStillUrl } from "./createApi";
import { CreateEvent, CreateJobDetail, CreatePhase, CreateStillOut } from "./createTypes";

export interface CreateStillTile {
  index: number;
  filename: string;
  file_url: string;
  handoff_filename: string;
  handoff_url: string;
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
    return stills.map((s) =>
      s.index === tile.index
        ? {
            ...s,
            ...tile,
            // Don't wipe URLs with empty strings from partial SSE events.
            file_url: tile.file_url || s.file_url,
            handoff_url: tile.handoff_url || s.handoff_url,
            handoff_filename: tile.handoff_filename || s.handoff_filename,
          }
        : s,
    );
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
    // job-done is terminal for both success and failure — never clear a prior error.
    const failed = run.failed || !!run.error;
    return {
      ...run,
      phase: failed ? "failed" : "done",
      complete: true,
      failed,
      error: failed ? (run.error ?? "Create job failed") : run.error,
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
    const handoffFilename =
      ev.handoff_filename ||
      (ev.filename.endsWith(".png")
        ? ev.filename.replace(/\.png$/i, ".mp4")
        : `${ev.filename}.mp4`);
    const tile: CreateStillTile = {
      index: ev.index,
      filename: ev.filename,
      file_url: ev.file_url || "",
      handoff_filename: handoffFilename,
      handoff_url: ev.handoff_url || "",
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
    // Don't wipe a prior failure when a mid-run phase event arrives late.
    failed: run.failed,
    error: run.error,
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
    phase: detail.phase as CreatePhase,
    message: detail.message ?? next.message,
    stillsTotal: detail.count,
    error: detail.error ?? next.error,
  };
  if (detail.error || detail.phase === "failed" || detail.state === "failed") {
    next = reduceCreateEvent(next, {
      state: "failed",
      message: detail.error ?? detail.message ?? "Create job failed",
      error: detail.error ?? detail.message ?? "Create job failed",
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
    handoff_filename: s.handoff_filename,
    file_url: s.file_url || createStillUrl(jobId, s.filename),
    handoff_url: s.handoff_url || createHandoffUrl(jobId, s.handoff_filename),
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
