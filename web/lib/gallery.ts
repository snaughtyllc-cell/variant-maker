import { SourceOut } from "./types";

export function filterSources(sources: SourceOut[], mode: "all" | "shortfall"): SourceOut[] {
  return mode === "shortfall"
    ? sources.filter(s => s.shortfall > 0 || s.copy_status === "missing")
    : sources;
}

export function zipEmptyCopy(): string {
  return "Those videos never copied back from the GPU. Wait a moment and try Download ZIP again, or Regenerate.";
}

export function copyMissingCopy(): string {
  return "GPU finished, but videos didn't copy back to Studio. Retry copy, or Regenerate if that still fails.";
}

export function removePackCopy(running: boolean): string {
  return running
    ? "This pack is still generating. Removing it stops that Generate for everyone on this Studio URL. Files on Studio are deleted."
    : "Remove this pack from Gallery? Files on Studio are deleted. Drive uploads are not touched.";
}

export function filesReadyCount(source: SourceOut): number {
  return source.files_ready ?? source.delivered;
}

export function deliveryComplete(source: SourceOut): boolean {
  if (source.copy_status === "missing" || source.copy_status === "copying") return false;
  return filesReadyCount(source) >= source.requested && source.shortfall === 0;
}

export function isFileReady(variant: { file_ready?: boolean }): boolean {
  return variant.file_ready !== false;
}

/** JPEG look still for Gallery tiles. Empty = fall back to the mp4. */
export function galleryStillUrl(
  variant: { look_var_url?: string | null } | null | undefined,
): string | undefined {
  const still = (variant?.look_var_url || "").trim();
  return still || undefined;
}

export function sortSources(sources: SourceOut[], by: "newest"): SourceOut[] {
  if (by !== "newest") return sources;
  return [...sources].sort((a, b) => {
    const ta = a.created_utc ?? "";
    const tb = b.created_utc ?? "";
    if (ta !== tb) return tb.localeCompare(ta);
    return 0;
  });
}

/** `?v=<source_id>:<variant.index>` from the Gallery address bar. */
export function parseGalleryVariantQuery(
  raw: string | null | undefined,
): { sourceId: string; index: number } | null {
  if (!raw) return null;
  const colonIdx = raw.lastIndexOf(":");
  if (colonIdx <= 0) return null;
  const sourceId = raw.slice(0, colonIdx);
  const parsed = Number.parseInt(raw.slice(colonIdx + 1), 10);
  if (!sourceId || Number.isNaN(parsed)) return null;
  return { sourceId, index: parsed };
}

export function gallerySearchPath(sourceId?: string | null, index?: number | null): string {
  if (!sourceId || index == null) return "/gallery";
  return `/gallery?v=${sourceId}:${index}`;
}

/**
 * Update the address bar without a Next.js navigation.
 * `router.push` remounts Gallery (Suspense flash + dialog replay = "glitching").
 */
export function pushGallerySearch(path: string): void {
  if (typeof window === "undefined") return;
  if (`${window.location.pathname}${window.location.search}` === path) return;
  window.history.pushState(null, "", path);
}
