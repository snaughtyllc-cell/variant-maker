import { describe, it, expect } from "vitest";
import {
  DEFAULT_PER_VIDEO,
  MAX_PER_VIDEO,
  variantStepperHint,
} from "@/lib/variantStepperCopy";

describe("variantStepperCopy", () => {
  it("defaults Fast packs to 10, with room to reach the usual ~20", () => {
    expect(DEFAULT_PER_VIDEO).toBe(10);
    expect(MAX_PER_VIDEO).toBeGreaterThanOrEqual(20);
  });

  it("on Fast, mentions the usual ~20 pack and tapping up", () => {
    const hint = variantStepperHint("fast");
    expect(hint).toMatch(/~20/);
    expect(hint).toMatch(/tap/i);
    expect(hint).not.toMatch(/long|slow|wait|kill|minute/i);
  });

  it("is silent on HQ (throughput copy lives elsewhere)", () => {
    expect(variantStepperHint("hq")).toBeNull();
  });
});
