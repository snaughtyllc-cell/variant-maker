import { SourceOut } from "./types";

export function filterSources(sources: SourceOut[], mode: "all" | "shortfall"): SourceOut[] {
  return mode === "shortfall" ? sources.filter(s => s.shortfall > 0) : sources;
}

export function sortSources(sources: SourceOut[], by: "newest"): SourceOut[] {
  return by === "newest" ? [...sources].reverse() : sources;
}
