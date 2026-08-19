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

  it("allows iPhone 4K under 512 MB and rejects bigger dumps", () => {
    const reel = new File([new Uint8Array(1)], "IMG_0683.MOV", { type: "video/quicktime" });
    Object.defineProperty(reel, "size", { value: 204 * 1024 * 1024 });
    expect(tooLargeMessage(reel)).toBeNull();

    const dump = new File([new Uint8Array(1)], "long.mov", { type: "video/quicktime" });
    Object.defineProperty(dump, "size", { value: 600 * 1024 * 1024 });
    expect(tooLargeMessage(dump)).toMatch(/600 MB/);
    expect(tooLargeMessage(dump)).toMatch(/512 MB/);
  });
});
