import { describe, it, expect } from "vitest";
import { filterSources, sortSources } from "@/lib/gallery";
const mk = (id: string, shortfall: number) => ({ source_id: id, filename: id, requested: 5, delivered: 5 - shortfall, shortfall, variants: [] });
describe("gallery helpers", () => {
  it("filter shortfall keeps only under-delivered", () => {
    const all = [mk("a", 0), mk("b", 2)];
    expect(filterSources(all, "shortfall").map(s => s.source_id)).toEqual(["b"]);
    expect(filterSources(all, "all").length).toBe(2);
  });
  it("sort newest reverses insertion order", () => {
    const all = [mk("a", 0), mk("b", 0)];
    expect(sortSources(all, "newest").map(s => s.source_id)).toEqual(["b", "a"]);
  });
});
