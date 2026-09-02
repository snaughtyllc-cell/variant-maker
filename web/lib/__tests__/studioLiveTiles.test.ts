import { describe, expect, it } from "vitest";
import { liveRowThumbSrc, liveTileLabel, liveTileMediaSrc, liveTilePreviewSrc, packLiveTiles } from "@/lib/studioLiveTiles";
import type { SourceProgress } from "@/lib/progress";

const quality = {
  vmaf: 96,
  histogram_ok: true,
  regen_count: 0,
  passed: true,
  spatial_vmaf: null,
  spatial_ok: null,
};

const source: SourceProgress = {
  source_id: "s1",
  filename: "clip.mp4",
  requested: 3,
  delivered: 1,
  done: 1,
  inFlights: { 2: { index: 2, state: "rendering", attempt: 0, max_attempts: 3 } },
  variants: [
    {
      index: 1,
      filename: "v01.mp4",
      status: "ok",
      quality,
      file_url: "/api/variants/s1/v01.mp4",
      uniqueness: 0.55,
    },
  ],
};

describe("packLiveTiles", () => {
  it("mixes a finished thumb with a live overlay and a queued slot", () => {
    const tiles = packLiveTiles(source);
    expect(tiles.map((t) => t.kind)).toEqual(["done", "live", "waiting"]);
    expect(tiles[0].variant?.file_url).toMatch(/v01/);
    expect(liveTileLabel(tiles[0])).toBe("55%");
    expect(liveTileLabel(tiles[1])).toBe("rendering");
    expect(liveTileLabel(tiles[2])).toBe("queued");
    expect(liveTileLabel(tiles[2], true)).toBe("starting");
  });

  it("uses the finished file for done tiles and the source poster while rendering", () => {
    const tiles = packLiveTiles(source);
    expect(liveTilePreviewSrc(source)).toBe("/api/sources/s1/source");
    expect(liveTileMediaSrc(tiles[0], source)).toMatch(/v01/);
    expect(liveTileMediaSrc(tiles[1], source)).toBe("/api/sources/s1/source");
    expect(liveRowThumbSrc(source)).toMatch(/v01/);
    expect(liveTilePreviewSrc({ ...source, source_id: "prep-1" })).toBeNull();
  });
});
