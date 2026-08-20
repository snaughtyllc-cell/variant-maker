import { describe, it, expect } from "vitest";
import {
  copyMissingCopy,
  deliveryComplete,
  filesReadyCount,
  filterSources,
  isFileReady,
  sortSources,
  zipEmptyCopy,
  removePackCopy,
} from "@/lib/gallery";
const mk = (id: string, shortfall: number, created_utc = "") => ({
  source_id: id, filename: id, requested: 5, delivered: 5 - shortfall, shortfall,
  variants: [], created_utc,
});
describe("gallery helpers", () => {
  it("filter shortfall keeps only under-delivered", () => {
    const all = [mk("a", 0), mk("b", 2)];
    expect(filterSources(all, "shortfall").map(s => s.source_id)).toEqual(["b"]);
    expect(filterSources(all, "all").length).toBe(2);
  });
  it("filter shortfall also keeps packs whose files never copied back", () => {
    const all = [
      mk("a", 0),
      { ...mk("ghost", 0), copy_status: "missing" as const, files_ready: 0 },
    ];
    expect(filterSources(all, "shortfall").map(s => s.source_id)).toEqual(["ghost"]);
    expect(filterSources(all, "all").length).toBe(2);
  });
  it("sort newest uses created_utc, not filename", () => {
    const all = [
      { ...mk("apple", 0), created_utc: "2026-01-01T00:00:00Z" },
      { ...mk("zebra", 0), created_utc: "2026-08-18T12:00:00Z" },
    ];
    expect(sortSources(all, "newest").map(s => s.source_id)).toEqual(["zebra", "apple"]);
  });
  it("explains an empty zip as missing GPU copies, not a Files app glitch", () => {
    expect(zipEmptyCopy()).toMatch(/copied back from the GPU/i);
  });

  it("does not treat metadata delivery as files on Studio", () => {
    const missing = {
      ...mk("ghost", 0),
      delivered: 5,
      files_ready: 0,
      copy_status: "missing" as const,
    };
    expect(filesReadyCount(missing)).toBe(0);
    expect(deliveryComplete(missing)).toBe(false);
    expect(copyMissingCopy()).toMatch(/Retry copy/i);
  });

  it("explains removing a pack, including a live one", () => {
    expect(removePackCopy(false)).toMatch(/Gallery/i);
    expect(removePackCopy(true)).toMatch(/still generating/i);
    expect(removePackCopy(true)).toMatch(/everyone on this Studio/i);
  });

  it("treats omitted file_ready as present (older Studio payloads)", () => {
    expect(isFileReady({ file_url: "/x" } as never)).toBe(true);
    expect(isFileReady({ file_url: "/x", file_ready: false } as never)).toBe(false);
  });
});
