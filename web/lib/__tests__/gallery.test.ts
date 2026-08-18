import { describe, it, expect } from "vitest";
import { filterSources, sortSources } from "@/lib/gallery";
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
  it("sort newest uses created_utc, not filename", () => {
    const all = [
      { ...mk("apple", 0), created_utc: "2026-01-01T00:00:00Z" },
      { ...mk("zebra", 0), created_utc: "2026-08-18T12:00:00Z" },
    ];
    expect(sortSources(all, "newest").map(s => s.source_id)).toEqual(["zebra", "apple"]);
  });
});
