export interface Quality {
  vmaf: number; histogram_ok: boolean; regen_count: number; passed: boolean;
  spatial_vmaf: number | null; spatial_ok: boolean | null;
}
export type Status = "ok" | "best_effort" | "corrupt";
export type PlatformResult = "passed" | "duplicate_reject" | "unknown";
export interface VariantOut {
  index: number; filename: string; status: Status; quality: Quality; file_url: string;
  uniqueness?: number | null; uniqueness_status?: string | null;
  uniqueness_metric?: string | null; uniqueness_target?: number | null;
  preset_used?: string | null; strength_final?: number | null;
  escalated?: boolean; platform_result?: PlatformResult | null;
}
export interface SourceOut { source_id: string; filename: string; requested: number; delivered: number; shortfall: number; variants: VariantOut[]; }
export interface JobSummary { job_id: string; count: number; created_utc: string; state: "running" | "done"; source_count: number; }
export interface JobDetail { job_id: string; count: number; created_utc: string; state: string; sources: SourceOut[]; }
export interface CreateJobResponse { job_id: string; sources: SourceOut[]; }
export interface DiagnosticsItem { source_id: string; index: number; filename: string; status: "best_effort" | "corrupt"; quality: Quality; }
export interface VariantEvent {
  source_id: string; index: number;
  state: "rendering" | "checking" | "rerolling" | "uniqueness" | "escalating" | "done";
  attempt: number; max_attempts: number;
  status: string | null; quality: Quality | null; filename: string | null;
  // Not present on raw SSE events; populated when synthesized from a polled VariantOut.
  uniqueness?: number | null; escalated?: boolean; platform_result?: PlatformResult | null;
}
export const VMAF_FLOOR = 90;
