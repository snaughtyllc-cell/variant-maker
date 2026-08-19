import { describe, it, expect } from "vitest";
import {
  captionBankChatPrompt,
  captionFilenamePreview,
  captionFolderCountLabel,
  captionFolderLowCopy,
  captionFolderSelectLabel,
  splitCaptionBank,
} from "@/lib/captions";

describe("caption bank paste", () => {
  it("splits blocks on a --- line", () => {
    expect(splitCaptionBank("POV one\n#reels\n---\nSecond\n#fyp")).toEqual([
      "POV one\n#reels",
      "Second\n#fyp",
    ]);
  });

  it("splits ChatGPT numbered blocks when there is no ---", () => {
    expect(splitCaptionBank("1. POV: she looked back\n#reels\n\n2. Wait for it\n#fyp")).toEqual([
      "POV: she looked back\n#reels",
      "Wait for it\n#fyp",
    ]);
  });

  it("strips a markdown code fence", () => {
    expect(splitCaptionBank("```\nFirst #reels\n---\nSecond #fyp\n```")).toEqual([
      "First #reels",
      "Second #fyp",
    ]);
  });
});

describe("captionBankChatPrompt", () => {
  it("asks for --- separated captions and the topic", () => {
    const prompt = captionBankChatPrompt({ count: 20, topic: "dating POV Reels" });
    expect(prompt).toMatch(/exactly:\n---/);
    expect(prompt).toMatch(/20 captions/);
    expect(prompt).toMatch(/dating POV Reels/);
    expect(prompt).not.toMatch(/numbered list/i);
  });
});

describe("captionFolderCountLabel", () => {
  it("shows remaining vs total and a low warning", () => {
    expect(captionFolderCountLabel(40, 40)).toBe("40 left · 40 total");
    expect(captionFolderCountLabel(0, 0)).toBe("0 left");
    expect(captionFolderSelectLabel("Gym", 14, 3)).toBe("Gym — 3 left");
    expect(captionFolderSelectLabel("Cooking", 0, 0)).toBe("Cooking — 0 left");
    expect(captionFolderLowCopy(0, 0)).toMatch(/empty/i);
    expect(captionFolderLowCopy(14, 14)).toMatch(/low/i);
    expect(captionFolderLowCopy(40, 40)).toBeNull();
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
