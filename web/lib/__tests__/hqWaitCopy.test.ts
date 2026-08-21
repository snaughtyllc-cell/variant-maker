import { describe, it, expect } from "vitest";
import { HQ_RENDERING_HINT, inFlightRenderingLabel, liveRunSubcopy } from "@/lib/hqWaitCopy";

describe("hqWaitCopy", () => {
  it("fast rendering stays the short vNN line", () => {
    expect(inFlightRenderingLabel(1)).toBe("● v01 rendering…");
    expect(inFlightRenderingLabel(12, "fast")).toBe("● v12 rendering…");
  });

  it("HQ rendering names upscale so a silent first minute is not a hang", () => {
    expect(inFlightRenderingLabel(1, "hq")).toBe("● v01 HQ upscaling…");
    expect(liveRunSubcopy("hq")).toContain(HQ_RENDERING_HINT);
    expect(liveRunSubcopy("hq")).toMatch(/several minutes/i);
    expect(liveRunSubcopy("fast")).not.toMatch(/HQ upscale/i);
    expect(liveRunSubcopy("fast")).toMatch(/20 for one clip/i);
  });
});
