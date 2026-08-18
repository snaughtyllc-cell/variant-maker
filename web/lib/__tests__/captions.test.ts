import { describe, it, expect } from "vitest";
import { captionFilenamePreview, splitCaptionBank } from "@/lib/captions";

describe("caption bank paste", () => {
  it("splits blocks on a --- line", () => {
    expect(splitCaptionBank("POV one\n#reels\n---\nSecond\n#fyp")).toEqual([
      "POV one\n#reels",
      "Second\n#fyp",
    ]);
  });
});

describe("captionFilenamePreview", () => {
  it("is the Drive name Repurpose will read as the caption", () => {
    expect(captionFilenamePreview("Wait for it 💕\n#reels")).toBe("Wait for it 💕 #reels.mp4");
    expect(captionFilenamePreview("POV: she said #reels")).toBe("POV: she said #reels.mp4");
  });

  it("falls back when the caption is empty", () => {
    expect(captionFilenamePreview("   ", "v01.mp4")).toBe("v01.mp4");
  });
});
