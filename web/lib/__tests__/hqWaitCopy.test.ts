import { describe, it, expect } from "vitest";
import {
  HQ_RENDERING_HINT,
  inFlightLookingLabel,
  inFlightRenderingLabel,
  inFlightSlotLabel,
  inFlightSummaryLine,
  liveRunSubcopy,
  reconstructFirstHeadline,
  reconstructFirstSubcopy,
} from "@/lib/hqWaitCopy";

describe("hqWaitCopy", () => {
  it("fast rendering stays the short vNN line", () => {
    expect(inFlightRenderingLabel(1)).toBe("● v01 rendering…");
    expect(inFlightRenderingLabel(12, "fast")).toBe("● v12 rendering…");
  });

  it("looking is a visual check, not uniqueness", () => {
    expect(inFlightLookingLabel(1)).toBe("● v01 looking…");
  });

  it("HQ rendering names upscale so a silent first minute is not a hang", () => {
    expect(inFlightRenderingLabel(1, "hq")).toBe("● v01 HQ upscaling…");
    expect(liveRunSubcopy("hq")).toContain(HQ_RENDERING_HINT);
    expect(liveRunSubcopy("hq")).toMatch(/several minutes/i);
    expect(liveRunSubcopy("fast")).not.toMatch(/HQ upscale/i);
    expect(liveRunSubcopy("fast")).toMatch(/20 for one clip/i);
    expect(liveRunSubcopy("fast")).toMatch(/tile/i);
  });

  it("reconstruct-first copy names the one GPU pass before Fast", () => {
    expect(reconstructFirstHeadline()).toMatch(/Reconstruct/i);
    expect(reconstructFirstSubcopy()).toMatch(/one HQ/i);
    expect(reconstructFirstSubcopy()).toMatch(/Fast/i);
    expect(reconstructFirstSubcopy()).not.toMatch(/20 HQ/i);
  });

  it("slot labels stay short on the tile", () => {
    expect(inFlightSlotLabel("waiting")).toBe("queued");
    expect(inFlightSlotLabel("rendering")).toBe("render");
    expect(inFlightSlotLabel("rendering", "hq")).toBe("HQ");
    expect(inFlightSlotLabel("looking")).toBe("look");
  });

  it("summarizes parallel copies without hopping to one vNN", () => {
    expect(inFlightSummaryLine([{ index: 1, state: "rendering" }])).toBe("● v01 rendering…");
    expect(inFlightSummaryLine([
      { index: 1, state: "rendering" },
      { index: 2, state: "rendering" },
    ])).toBe("2 rendering");
    expect(inFlightSummaryLine(
      Array.from({ length: 8 }, (_, i) => ({ index: i + 1, state: "rendering" })),
    )).toBe("8 rendering");
    expect(inFlightSummaryLine([
      { index: 1, state: "rendering" },
      { index: 2, state: "looking" },
    ])).toBe("1 rendering · 1 looking");
  });
});
