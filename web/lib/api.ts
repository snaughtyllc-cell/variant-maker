import { CreateJobResponse, DiagnosticsItem, JobDetail, JobSummary, PlatformResult, SourceOut, VariantOut } from "./types";

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

export function createJob(files: File[], count: number): Promise<CreateJobResponse> {
  const fd = new FormData();
  fd.append("count", String(count));
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
