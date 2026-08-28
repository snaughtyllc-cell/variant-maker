import { describe, expect, it } from "vitest";
import {
  PREPARING_JOB_ID,
  captionSnippet,
  captionToggleHint,
  captionToggleLabel,
  isPreparingJob,
  preparingHeadline,
  preparingSubcopy,
  uniquenessCoverageChips,
  uniquenessCoverageSubcopy,
  uniquenessCustomerLabel,
  uniquenessGalleryBadgeTitle,
} from "@/lib/prepareCopy";

describe("prepare copy", () => {
  it("names the early progress state", () => {
    expect(isPreparingJob(PREPARING_JOB_ID)).toBe(true);
    expect(isPreparingJob("abc")).toBe(false);
    expect(preparingHeadline()).toMatch(/preparing generation/i);
    expect(preparingSubcopy()).toMatch(/20–30 seconds/i);
    expect(preparingSubcopy()).toMatch(/request received/i);
  });

  it("asks for captions on Generate, not a separate bank UI", () => {
    expect(captionToggleLabel()).toMatch(/write captions/i);
    expect(captionToggleHint()).toMatch(/gallery/i);
    expect(uniquenessCustomerLabel()).toBe("Originality");
  });

  it("names Originality as 3-frame pixel SSIM, not a platform check", () => {
    expect(uniquenessCoverageSubcopy()).toMatch(/pixel difference vs the original/i);
    expect(uniquenessCoverageSubcopy()).toMatch(/3 frames/i);
    expect(uniquenessCoverageSubcopy()).toMatch(/not a platform check/i);
    expect(uniquenessGalleryBadgeTitle(50)).toMatch(/50%/);
    expect(uniquenessGalleryBadgeTitle(50)).toMatch(/pixel SSIM/i);
    expect(uniquenessGalleryBadgeTitle(50)).toMatch(/not a platform pass/i);
  });

  it("marks pixel scored from uniqueness and leaves copy-id heads off by default", () => {
    const chips = uniquenessCoverageChips(0.5, null);
    expect(chips.map((c) => c.kind)).toEqual(["pixel", "visual", "audio"]);
    expect(chips[0]).toMatchObject({ kind: "pixel", state: "scored", text: "Pixel · scored" });
    expect(chips[1]).toMatchObject({
      kind: "visual",
      state: "not_scored",
      text: "Visual copy-id · not scored",
    });
    expect(chips[2]).toMatchObject({
      kind: "audio",
      state: "not_scored",
      text: "Audio · not scored",
    });
    expect(chips.every((c) => /not a platform/i.test(c.title))).toBe(true);
  });

  it("lights visual and audio chips only when those heads are available", () => {
    const chips = uniquenessCoverageChips(0.41, {
      ssim: { available: true, uniqueness: 0.41, bits: 26 },
      visual: { available: true, uniqueness: 0.22, backend: "sscd_disc_mixup" },
      audio: { available: true, uniqueness: 0.05 },
    });
    expect(chips[0].state).toBe("scored");
    expect(chips[1]).toMatchObject({ kind: "visual", state: "scored", text: "Visual copy-id · 22%" });
    expect(chips[2]).toMatchObject({ kind: "audio", state: "scored", text: "Audio · 5%" });
  });

  it("does not treat a missing uniqueness as a scored pixel head", () => {
    const chips = uniquenessCoverageChips(null, {
      visual: { available: false },
      audio: { uniqueness: 0.9 },
    });
    expect(chips[0].state).toBe("not_scored");
    expect(chips[1].state).toBe("not_scored");
    expect(chips[2].state).toBe("not_scored");
  });

  it("snips captions to a single-line preview", () => {
    expect(captionSnippet(null)).toBe("");
    expect(captionSnippet("  hello   world  ")).toBe("hello world");
    expect(captionSnippet("a".repeat(80))).toBe("a".repeat(80));
    expect(captionSnippet("a".repeat(81))).toBe(`${"a".repeat(79)}…`);
  });
});
