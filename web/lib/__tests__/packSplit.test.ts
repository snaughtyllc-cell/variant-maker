import { describe, expect, it } from "vitest";
import {
  assignedTotal,
  autoCountsForSlots,
  formatSlice,
  guessSlotDestinations,
  sliceRanges,
  splitSizes,
} from "@/lib/packSplit";

describe("splitSizes", () => {
  it("puts remainder on the first buckets", () => {
    expect(splitSizes(20, 3)).toEqual([7, 7, 6]);
    expect(splitSizes(10, 3)).toEqual([4, 3, 3]);
    expect(splitSizes(20, 2)).toEqual([10, 10]);
    expect(splitSizes(21, 2)).toEqual([11, 10]);
    expect(splitSizes(20, 1)).toEqual([20]);
  });

  it("returns empty when nothing is filled", () => {
    expect(splitSizes(20, 0)).toEqual([]);
  });
});

describe("autoCountsForSlots", () => {
  it("only assigns to filled destination slots", () => {
    expect(autoCountsForSlots(20, ["a", "b", "c"])).toEqual([7, 7, 6]);
    expect(autoCountsForSlots(20, ["a", "b", ""])).toEqual([10, 10, 0]);
    expect(autoCountsForSlots(20, ["a", "", ""])).toEqual([20, 0, 0]);
    expect(autoCountsForSlots(20, ["", "", ""])).toEqual([0, 0, 0]);
  });
});

describe("assignedTotal / formatSlice", () => {
  it("sums counts and labels 1-based ranges", () => {
    expect(assignedTotal([7, 7, 6])).toBe(20);
    expect(assignedTotal([10, 10, 0])).toBe(20);
    expect(formatSlice(1, 7, 7)).toBe("7 files · 1–7");
    expect(formatSlice(15, 20, 6)).toBe("6 files · 15–20");
    expect(formatSlice(1, 0, 0)).toBe("0 files");
    const ranges = sliceRanges([7, 7, 6]);
    expect(ranges.map((r) => `${r.start}–${r.end}`)).toEqual(["1–7", "8–14", "15–20"]);
  });
});

describe("guessSlotDestinations", () => {
  it("matches saved folders by role name, not position", () => {
    expect(
      guessSlotDestinations([
        { id: "g", name: "Maya / growth" },
        { id: "m", name: "Maya / main" },
        { id: "t", name: "Maya / trial" },
      ]),
    ).toEqual(["m", "t", "g"]);
  });

  it("leaves a slot empty when nothing is named for that role", () => {
    expect(
      guessSlotDestinations([{ id: "out", name: "Reels outbox" }]),
    ).toEqual(["", "", ""]);
  });
});
