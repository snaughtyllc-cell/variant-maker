import { CreateJobResponse, Destination, DiagnosticsItem, DriveStatus, ExportJob, ExportVariantRef, JobDetail, JobSummary, PlatformResult, SourceOut, VariantOut } from "./types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const variantUrl = (sourceId: string, filename: string) => `/api/variants/${sourceId}/${filename}`;
export const sourceUrl = (sourceId: string) => `/api/sources/${sourceId}/source`;
export const eventsUrl = (jobId: string) => `/api/jobs/${jobId}/events`;
export const sourceZipUrl = (sourceId: string) => `/api/sources/${sourceId}/zip`;

export const getHealth = () => fetch("/api/health").then(json<{ status: string }>);
export const getJobs = () => fetch("/api/jobs").then(json<JobSummary[]>);
export const getJob = (id: string) => fetch(`/api/jobs/${id}`).then(json<JobDetail>);
export const getGallery = () => fetch("/api/gallery").then(json<SourceOut[]>);
export const getDiagnostics = () => fetch("/api/diagnostics").then(json<DiagnosticsItem[]>);

export function createJob(
  files: File[],
  count: number,
  allowCreativeEscalate: boolean = true,
): Promise<CreateJobResponse> {
  const fd = new FormData();
  fd.append("count", String(count));
  fd.append("allow_creative_escalate", String(allowCreativeEscalate));
  for (const f of files) fd.append("files", f, f.name);
  return fetch("/api/jobs", { method: "POST", body: fd }).then(json<CreateJobResponse>);
}

export function regenerate(sourceId: string, n: number): Promise<SourceOut> {
  const fd = new FormData();
  fd.append("n", String(n));
  return fetch(`/api/sources/${sourceId}/regenerate`, { method: "POST", body: fd }).then(json<SourceOut>);
}

export function setPlatformResult(sourceId: string, index: number, result: PlatformResult): Promise<VariantOut> {
  return fetch(`/api/variants/${sourceId}/${index}/platform-result`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ result }),
  }).then(json<VariantOut>);
}

export const getDriveStatus = () => fetch("/api/drive/status").then(json<DriveStatus>);

export const listDestinations = () => fetch("/api/drive/destinations").then(json<Destination[]>);

export function createDestination(name: string, folderUrl: string): Promise<Destination> {
  return fetch("/api/drive/destinations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, folder_url: folderUrl }),
  }).then(json<Destination>);
}

export function updateDestination(
  id: string,
  patch: { name?: string; folder_url?: string },
): Promise<Destination> {
  return fetch(`/api/drive/destinations/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  }).then(json<Destination>);
}

export async function deleteDestination(id: string): Promise<void> {
  const res = await fetch(`/api/drive/destinations/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
}

export const testDestination = (id: string) =>
  fetch(`/api/drive/destinations/${id}/test`, { method: "POST" }).then(json<{ ok: boolean }>);

export function createDriveExport(destinationId: string, variants: ExportVariantRef[]): Promise<ExportJob> {
  return fetch("/api/drive/exports", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ destination_id: destinationId, variants }),
  }).then(json<ExportJob>);
}

export const getDriveExport = (exportId: string) =>
  fetch(`/api/drive/exports/${exportId}`, { cache: "no-store" }).then(json<ExportJob>);

export const retryDriveExport = (exportId: string) =>
  fetch(`/api/drive/exports/${exportId}/retry`, { method: "POST" }).then(json<ExportJob>);
