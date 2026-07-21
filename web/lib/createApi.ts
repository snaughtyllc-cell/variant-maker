import {
  CreateAspect,
  CreateJobDetail,
  CreateJobResponse,
  LoraOut,
  LoraTrainStatus,
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
  faceRefs?: File[];
  loraId?: string | null;
  loraStrength?: number | null;
}

/** POST multipart create job: brief + aspect + count + face_refs and/or lora_id. */
export function createCreateJob(input: CreateJobInput): Promise<CreateJobResponse> {
  const fd = new FormData();
  fd.append("brief", input.brief);
  fd.append("aspect", input.aspect);
  fd.append("count", String(input.count));
  for (const f of input.faceRefs ?? []) fd.append("face_refs", f, f.name);
  if (input.loraId) fd.append("lora_id", input.loraId);
  if (input.loraStrength != null) fd.append("lora_strength", String(input.loraStrength));
  return fetch("/api/create/jobs", { method: "POST", body: fd }).then(
    json<CreateJobResponse>,
  );
}

export const listLoras = () =>
  fetch("/api/create/loras", { cache: "no-store" }).then(json<LoraOut[]>);

export interface UploadLoraInput {
  name: string;
  file: File;
  triggerWord?: string;
  defaultStrength?: number;
}

export function uploadLora(input: UploadLoraInput): Promise<LoraOut> {
  const fd = new FormData();
  fd.append("name", input.name);
  fd.append("file", input.file, input.file.name);
  if (input.triggerWord) fd.append("trigger_word", input.triggerWord);
  if (input.defaultStrength != null) {
    fd.append("default_strength", String(input.defaultStrength));
  }
  return fetch("/api/create/loras", { method: "POST", body: fd }).then(json<LoraOut>);
}

export function deleteLora(id: string): Promise<void> {
  return fetch(`/api/create/loras/${id}`, { method: "DELETE" }).then(async (res) => {
    if (!res.ok && res.status !== 204) {
      await json(res);
    }
  });
}

export function requestLoraTrain(input: {
  name: string;
  photos: File[];
}): Promise<LoraTrainStatus> {
  const fd = new FormData();
  fd.append("name", input.name);
  for (const f of input.photos) fd.append("photos", f, f.name);
  return fetch("/api/create/loras/train", { method: "POST", body: fd }).then(
    json<LoraTrainStatus>,
  );
}
