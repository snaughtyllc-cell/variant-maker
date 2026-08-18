import { CreateJobResponse, Destination, DiagnosticsItem, DriveStatus, ExportJob, ExportVariantRef, JobDetail, JobSummary, PlatformResult, SourceOut, VariantOut } from "./types";

/**
 * FastAPI error bodies are `{"detail": string | Array<{msg: string, ...}>}`.
 * Prefer that over the generic status text so actionable messages (e.g. Drive
 * permission/quota errors) reach the UI instead of "400 Bad Request".
 */
async function errorMessage(res: Response): Promise<string> {
  const fallback = `${res.status} ${res.statusText}`;
  try {
    const body = await res.clone().json();
    const detail = body?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail) && detail.length) {
      return detail
        .map((d) => (typeof d === "string" ? d : d?.msg ?? JSON.stringify(d)))
        .join("; ");
    }
  } catch {
    // Body wasn't JSON (or was empty) — fall back to status text below.
  }
  return fallback;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json() as Promise<T>;
}

export const variantUrl = (sourceId: string, filename: string) => `/api/variants/${sourceId}/${filename}`;
export const sourceUrl = (sourceId: string) => `/api/sources/${sourceId}/source`;
export const eventsUrl = (jobId: string) => `/api/jobs/${jobId}/events`;
export const sourceZipUrl = (sourceId: string) => `/api/sources/${sourceId}/zip`;

export const getHealth = () => fetch("/api/health").then(json<{ status: string }>);
export const getJobs = () => fetch("/api/jobs").then(json<JobSummary[]>);
export const getJob = (id: string) =>
  fetch(`/api/jobs/${id}`, { cache: "no-store" }).then(json<JobDetail>);
export const getGallery = () => fetch("/api/gallery").then(json<SourceOut[]>);
export const getDiagnostics = () => fetch("/api/diagnostics").then(json<DiagnosticsItem[]>);

/** RunPod's HTTP proxy often drops multipart bodies above a few MB — chunk instead. */
const CHUNK_THRESHOLD = 3_500_000;
const CHUNK_SIZE = 2_000_000;

async function uploadFileChunked(file: File): Promise<string> {
  const initFd = new FormData();
  initFd.append("filename", file.name);
  initFd.append("size", String(file.size));
  const init = await fetch("/api/uploads", { method: "POST", body: initFd }).then(
    json<{ upload_id: string; chunk_hint?: number }>,
  );
  const chunkSize = init.chunk_hint || CHUNK_SIZE;
  let offset = 0;
  while (offset < file.size) {
    const blob = file.slice(offset, offset + chunkSize);
    const buf = await blob.arrayBuffer();
    const res = await fetch(`/api/uploads/${init.upload_id}?offset=${offset}`, {
      method: "PUT",
      headers: { "Content-Type": "application/octet-stream" },
      body: buf,
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    offset += blob.size;
  }
  return init.upload_id;
}

export async function createJob(
  files: File[],
  count: number,
  allowCreativeEscalate: boolean = true,
): Promise<CreateJobResponse> {
  const needsChunk = files.some((f) => f.size > CHUNK_THRESHOLD);
  if (!needsChunk) {
    const fd = new FormData();
    fd.append("count", String(count));
    fd.append("allow_creative_escalate", String(allowCreativeEscalate));
    for (const f of files) fd.append("files", f, f.name);
    return fetch("/api/jobs", { method: "POST", body: fd }).then(json<CreateJobResponse>);
  }

  const uploadIds: string[] = [];
  for (const f of files) {
    uploadIds.push(await uploadFileChunked(f));
  }
  const fd = new FormData();
  fd.append("upload_ids", uploadIds.join(","));
  fd.append("count", String(count));
  fd.append("allow_creative_escalate", String(allowCreativeEscalate));
  return fetch("/api/jobs/from-uploads", { method: "POST", body: fd }).then(json<CreateJobResponse>);
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

export async function disconnectDriveOAuth(): Promise<void> {
  const res = await fetch("/api/drive/oauth/disconnect", { method: "POST" });
  if (!res.ok) throw new Error(await errorMessage(res));
}

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
  if (!res.ok) throw new Error(await errorMessage(res));
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
