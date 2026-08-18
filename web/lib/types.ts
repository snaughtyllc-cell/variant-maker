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
  file_ready?: boolean;
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
  created_utc?: string | null;
  files_ready?: number;
  copy_status?: "ok" | "copying" | "missing";
}
export interface JobSummary { job_id: string; count: number; created_utc: string; state: "running" | "done"; source_count: number; }
export interface JobDetail { job_id: string; count: number; created_utc: string; state: string; sources: SourceOut[]; error?: string | null; }
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
  caption?: string | null;
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

export interface DriveVideo {
  id: string;
  name: string;
  mime_type: string;
  md5: string | null;
}

export interface WorkflowSummary {
  queued: number;
  exported: number;
  skipped: number;
  failed: number;
  running: number;
  job_ids: string[];
  error?: string | null;
}

export interface Caption {
  id: string;
  text: string;
}

export interface CaptionBank {
  cursor: number;
  items: Caption[];
}

export interface Workflow {
  id: string;
  name: string;
  inbox_destination_id: string;
  output_destination_id: string;
  count: number;
  quality_mode: "fast" | "hq";
  allow_creative_escalate: boolean;
  enabled: boolean;
  poll_seconds: number;
  last_sweep_at: string | null;
  last_summary: WorkflowSummary | null;
  auto_caption: boolean;
}
