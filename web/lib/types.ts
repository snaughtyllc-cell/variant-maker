export interface Quality {
  vmaf: number; histogram_ok: boolean; regen_count: number; passed: boolean;
  spatial_vmaf: number | null; spatial_ok: boolean | null;
}
export type Status = "ok" | "best_effort" | "corrupt";
export type PlatformResult = "passed" | "duplicate_reject" | "flagged" | "unknown";
export interface VariantOut {
  index: number; filename: string; status: Status; quality: Quality; file_url: string;
  uniqueness?: number | null; uniqueness_status?: string | null;
  uniqueness_metric?: string | null; uniqueness_target?: number | null;
  preset_used?: string | null; strength_final?: number | null;
  escalated?: boolean; platform_result?: PlatformResult | null;
}
export interface InFlightOut {
  index: number;
  state: "rendering" | "checking" | "rerolling" | "uniqueness" | "escalating";
  attempt: number;
  max_attempts: number;
}
export interface SourceOut {
  source_id: string; filename: string; requested: number; delivered: number; shortfall: number;
  variants: VariantOut[];
  in_flight?: InFlightOut | null;
  job_state?: "running" | "done" | string | null;
  failed?: number;
}
export interface JobSummary { job_id: string; count: number; created_utc: string; state: "running" | "done"; source_count: number; }
export interface JobDetail { job_id: string; count: number; created_utc: string; state: string; sources: SourceOut[]; }
export interface CreateJobResponse { job_id: string; sources: SourceOut[]; }
export interface DiagnosticsItem { source_id: string; index: number; filename: string; status: "best_effort" | "corrupt"; quality: Quality; }
export interface VariantEvent {
  source_id: string; index: number;
  state: "rendering" | "checking" | "rerolling" | "uniqueness" | "escalating" | "done";
  attempt: number; max_attempts: number;
  status: string | null; quality: Quality | null; filename: string | null;
  uniqueness?: number | null;
  uniqueness_status?: string | null;
  uniqueness_metric?: string | null;
  uniqueness_target?: number | null;
  escalated?: boolean;
  platform_result?: PlatformResult | null;
}
export const VMAF_FLOOR = 90;

export type DriveStatusValue = "ready" | "not_configured" | "auth_failed";
export interface DriveStatus {
  status: DriveStatusValue;
  sa_email: string | null;
  message: string;
  auth_mode?: string | null;
  connected_email?: string | null;
  oauth_available?: boolean;
}
export interface Destination {
  id: string;
  name: string;
  folder_id: string;
  auth_mode: string;
}
export interface ExportVariantRef {
  source_id: string;
  index: number;
}
export interface ExportFile {
  source_id: string;
  index: number;
  filename: string;
  status: string;
  error?: string | null;
  drive_file_id?: string | null;
}
export interface ExportJob {
  export_id: string;
  destination_id: string;
  folder_id: string;
  state: string;
  created_utc: string;
  files: ExportFile[];
}
