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
