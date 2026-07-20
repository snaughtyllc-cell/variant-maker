/** Create-mode API types — aligned to backend create_models / create_api. */

export type CreateAspect = "9:16" | "1:1" | "16:9";

export type CreateJobState = "running" | "done" | "failed";

/** High-level job phase exposed on GET detail (and mapped from SSE). */
export type CreatePhase =
  | "queued"
  | "directing"
  | "generating"
  | "saving"
  | "done"
  | "failed";

export interface CreateStillOut {
  index: number;
  filename: string;
  handoff_filename: string;
  status: string;
  file_url: string;
  handoff_url: string;
}

export interface CreateJobSummary {
  job_id: string;
  count: number;
  aspect: CreateAspect;
  brief: string;
  created_utc: string;
  state: CreateJobState;
}

export interface CreateJobDetail {
  job_id: string;
  brief: string;
  aspect: CreateAspect;
  count: number;
  created_utc: string;
  state: CreateJobState;
  phase: CreatePhase;
  message: string | null;
  stills: CreateStillOut[];
  error: string | null;
  identities?: string[];
  prompt?: { positive: string; negative: string; notes?: string } | null;
}

/** Immediate response from POST /api/create/jobs. */
export interface CreateJobResponse {
  job_id: string;
  count: number;
  aspect: CreateAspect;
  brief: string;
  state: CreateJobState;
  created_utc: string;
}

/**
 * SSE / progress event for a create job (backend runner vocabulary).
 * `job-done` closes the stream; per-still completion uses `done` + filename.
 */
export interface CreateEvent {
  state:
    | CreatePhase
    | "expanding"
    | "expanded"
    | "handoff"
    | "still-done"
    | "job-done"
    | "error"
    | "done";
  index?: number | null;
  filename?: string | null;
  handoff_filename?: string | null;
  file_url?: string | null;
  status?: string | null;
  message?: string | null;
  error?: string | null;
  stills_done?: number;
  stills_total?: number;
  job_id?: string;
}

export const CREATE_ASPECTS: readonly CreateAspect[] = ["9:16", "1:1", "16:9"] as const;
export const CREATE_COUNT_MIN = 1;
export const CREATE_COUNT_MAX = 4;
export const CREATE_FACE_REF_MAX = 4;
