import { describe, expect, it } from "vitest";
import {
  PREPARING_JOB_ID,
  captionSnippet,
  captionToggleHint,
  captionToggleLabel,
  isPreparingJob,
  preparingHeadline,
  preparingSubcopy,
  uniquenessCustomerLabel,
  uniquenessPassHint,
  uniquenessPassPct,
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

  it("explains the real ~38% pass line, not a 65% verified band", () => {
    expect(uniquenessPassPct()).toBe(38);
    expect(uniquenessPassHint()).toBe("38% = pass vs the source");
    expect(uniquenessPassHint()).not.toMatch(/verified/i);
    expect(uniquenessPassHint()).not.toMatch(/65%/);
  });

  it("snips captions to a single-line preview", () => {
    expect(captionSnippet(null)).toBe("");
    expect(captionSnippet("  hello   world  ")).toBe("hello world");
    expect(captionSnippet("a".repeat(80))).toBe("a".repeat(80));
    expect(captionSnippet("a".repeat(81))).toBe(`${"a".repeat(79)}…`);
  });
});
