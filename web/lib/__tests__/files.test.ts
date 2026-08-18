import { describe, it, expect } from "vitest";
import { accepts, totalVariants } from "@/lib/files";

describe("files helpers", () => {
  it("accepts video files", () => {
    expect(accepts(new File([], "a.mp4", { type: "video/mp4" }))).toBe(true);
    expect(accepts(new File([], "a.mov", { type: "" }))).toBe(true);
    expect(accepts(new File([], "a.txt", { type: "text/plain" }))).toBe(false);
  });
  it("totalVariants multiplies per-video by file count", () => {
    expect(totalVariants(2, 20)).toBe(40);
    expect(totalVariants(0, 20)).toBe(0);
  });
});
