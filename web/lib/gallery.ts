import { SourceOut } from "./types";

export function filterSources(sources: SourceOut[], mode: "all" | "shortfall"): SourceOut[] {
  return mode === "shortfall" ? sources.filter(s => s.shortfall > 0) : sources;
}

export function zipEmptyCopy(): string {
  return "Those videos never copied back from the GPU. Wait a moment and try Download ZIP again, or Regenerate.";
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
