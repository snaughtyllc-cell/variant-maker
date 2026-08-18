import { describe, it, expect } from "vitest";
import { accepts, tooLargeMessage, totalVariants } from "@/lib/files";

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

  it("rejects files over 120 MB with an export hint", () => {
    const big = new File([new Uint8Array(1)], "camera.mov", { type: "video/quicktime" });
    Object.defineProperty(big, "size", { value: 253 * 1024 * 1024 });
    expect(tooLargeMessage(big)).toMatch(/253 MB/);
    expect(tooLargeMessage(big)).toMatch(/1080p/i);
    const ok = new File([new Uint8Array(1)], "clip.mp4", { type: "video/mp4" });
    Object.defineProperty(ok, "size", { value: 20 * 1024 * 1024 });
    expect(tooLargeMessage(ok)).toBeNull();
  });
});
