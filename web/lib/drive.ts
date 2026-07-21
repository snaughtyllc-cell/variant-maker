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
