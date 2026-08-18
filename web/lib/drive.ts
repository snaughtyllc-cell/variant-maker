import type { Destination, DriveStatus, ExportVariantRef, SourceOut } from "./types";

export function okVariantRefs(sources: SourceOut[], selected: Set<string>): ExportVariantRef[] {
  const refs: ExportVariantRef[] = [];
  for (const source of sources) {
    for (const variant of source.variants) {
      if (variant.status !== "ok") continue;
      if (!selected.has(`${source.source_id}:${variant.index}`)) continue;
      refs.push({ source_id: source.source_id, index: variant.index });
    }
  }
  return refs;
}

export function truncateFolderId(id: string, keep = 8): string {
  if (id.length <= keep * 2 + 1) return id;
  return `${id.slice(0, keep)}…${id.slice(-keep)}`;
}

export function sendDisabledReason(
  status: DriveStatus | null,
  destinations: Destination[],
  refs: ExportVariantRef[],
): string | null {
  if (!status || status.status !== "ready") {
    return status?.message ?? "Drive not configured on this Pod";
  }
  if (destinations.length === 0) {
    return "No Drive destinations saved";
  }
  if (refs.length === 0) {
    return "Select at least one ok variant";
  }
  return null;
}

export function exportProgressLabel(job: {
  files: { status: string; filename: string }[];
}): { done: number; total: number; current: string | null } {
  const total = job.files.length;
  const done = job.files.filter((f) => f.status === "succeeded" || f.status === "failed").length;
  const current = job.files.find((f) => f.status === "uploading")?.filename ?? null;
  return { done, total, current };
}
