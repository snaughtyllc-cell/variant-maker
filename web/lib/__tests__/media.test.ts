import { describe, it, expect } from "vitest";
import { clipInset, clampTime, previewTime, videoFrameSrc } from "@/lib/media";
describe("media helpers", () => {
  it("clipInset maps percent to inset", () => {
    expect(clipInset(54)).toBe("inset(0 46% 0 0)");
    expect(clipInset(0)).toBe("inset(0 100% 0 0)");
  });
  it("clampTime clamps to [0,duration]", () => {
    expect(clampTime(-1, 10)).toBe(0);
    expect(clampTime(5, 10)).toBe(5);
    expect(clampTime(99, 10)).toBe(10);
    expect(clampTime(5, 0)).toBe(0);
  });
});

describe("mobile first-frame helpers", () => {
  it("adds a media fragment so Safari can paint a frame", () => {
    expect(videoFrameSrc("/api/variants/s1/v01.mp4")).toBe("/api/variants/s1/v01.mp4#t=0.15");
  });

  it("does not double-hash an existing fragment", () => {
    expect(videoFrameSrc("/x.mp4#t=1")).toBe("/x.mp4#t=1");
  });

  it("keeps preview time inside short clips", () => {
    expect(previewTime(10)).toBe(0.15);
    expect(previewTime(0.2)).toBe(0.05);
    expect(previewTime(0)).toBe(0.15);
  });
});
