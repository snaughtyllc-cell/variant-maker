import {
  CreateAspect,
  CreateJobDetail,
  CreateJobResponse,
} from "./createTypes";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      // ignore non-JSON error bodies
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const createStillUrl = (jobId: string, filename: string) =>
  `/api/create/jobs/${jobId}/files/${filename}`;

export const createHandoffUrl = (jobId: string, filename: string) =>
  `/api/create/jobs/${jobId}/files/${filename}`;

export const createEventsUrl = (jobId: string) => `/api/create/jobs/${jobId}/events`;

export const getCreateJob = (id: string) =>
  fetch(`/api/create/jobs/${id}`, { cache: "no-store" }).then(json<CreateJobDetail>);

export const getCreateJobs = () =>
  fetch("/api/create/jobs", { cache: "no-store" }).then(json<CreateJobDetail[]>);

export interface CreateJobInput {
  brief: string;
  aspect: CreateAspect;
  count: number;
  faceRefs: File[];
}

/** POST multipart create job: brief + aspect + count + face_refs. */
export function createCreateJob(input: CreateJobInput): Promise<CreateJobResponse> {
  const fd = new FormData();
  fd.append("brief", input.brief);
  fd.append("aspect", input.aspect);
  fd.append("count", String(input.count));
  for (const f of input.faceRefs) fd.append("face_refs", f, f.name);
  return fetch("/api/create/jobs", { method: "POST", body: fd }).then(
    json<CreateJobResponse>,
  );
}
