import { sourceUrl } from "./api";
import type { InFlight, SourceProgress, VariantTile } from "./progress";

export type LiveTileKind = "done" | "live" | "waiting";

export interface LiveTile {
  index: number;
  kind: LiveTileKind;
  variant?: VariantTile;
  flight?: InFlight;
}

/** One tile per requested copy: finished thumb, live status, or queued. */
export function packLiveTiles(source: SourceProgress): LiveTile[] {
  const byIndex = new Map(source.variants.map((v) => [v.index, v]));
  const flights = source.inFlights || {};
  const n = Math.max(source.requested, source.variants.length);
  const tiles: LiveTile[] = [];
  for (let index = 1; index <= n; index++) {
    const variant = byIndex.get(index);
    if (variant?.file_url) {
      tiles.push({ index, kind: "done", variant });
      continue;
    }
    const flight = flights[index];
    tiles.push({
      index,
      kind: flight ? "live" : "waiting",
      flight,
    });
  }
  return tiles;
}

export function liveTileLabel(tile: LiveTile, preparing = false): string {
  if (tile.kind === "done") {
    const pct = tile.variant?.uniqueness != null ? Math.round(tile.variant.uniqueness * 100) : null;
    return pct != null ? `${pct}%` : "ready";
  }
  if (tile.kind === "live") return tile.flight?.state ?? "render";
  return preparing ? "starting" : "queued";
}

/** Source poster while copies are still rendering. Prep ids have no file yet. */
export function liveTilePreviewSrc(source: SourceProgress): string | null {
  if (source.source_id && !source.source_id.startsWith("prep-")) {
    return sourceUrl(source.source_id);
  }
  return null;
}

export function liveTileMediaSrc(tile: LiveTile, source: SourceProgress): string | null {
  if (tile.kind === "done" && tile.variant?.file_url) return tile.variant.file_url;
  return liveTilePreviewSrc(source);
}

export function liveRowThumbSrc(source: SourceProgress | undefined): string | null {
  if (!source) return null;
  return source.variants.find((v) => v.file_url)?.file_url ?? liveTilePreviewSrc(source);
}
