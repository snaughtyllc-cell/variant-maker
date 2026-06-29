import { describe, it, expect } from "vitest";
import { formatDuration, vmafPass, diagnosticsReason } from "@/lib/format";

describe("formatDuration", () => {
  it("formats seconds as m:ss", () => {
    expect(formatDuration(18)).toBe("0:18");
    expect(formatDuration(42)).toBe("0:42");
    expect(formatDuration(95)).toBe("1:35");
  });
});

describe("vmafPass", () => {
  it("passes at or above floor 90", () => {
    expect(vmafPass(90)).toBe(true);
    expect(vmafPass(84.2)).toBe(false);
  });
});

describe("diagnosticsReason", () => {
  const q = (over: Partial<any>) => ({ vmaf: 84.2, histogram_ok: true, regen_count: 3, passed: false, spatial_vmaf: null, spatial_ok: null, ...over });
  it("below-floor reason carries the vmaf metric", () => {
    const r = diagnosticsReason({ source_id: "s", index: 19, filename: "v19.mp4", status: "best_effort", quality: q({}) });
    expect(r.corrupt).toBe(false);
    expect(r.metric).toContain("84.2");
    expect(r.metric).toContain("90");
  });
  it("corrupt reason carries the spatial metric", () => {
    const r = diagnosticsReason({ source_id: "s", index: 7, filename: "v07.mp4", status: "corrupt", quality: q({ passed: false, spatial_ok: false, spatial_vmaf: 22.0 }) });
    expect(r.corrupt).toBe(true);
    expect(r.metric).toContain("22");
  });
});
