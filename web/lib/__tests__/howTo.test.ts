import { describe, expect, it } from "vitest";
import { HOW_TO_FORBIDDEN, HOW_TO_SECTIONS, howToPlainText } from "../howTo";

describe("howTo copy", () => {
  it("is case scenarios, not a Generate walkthrough or HQ pitch", () => {
    const text = howToPlainText();
    expect(HOW_TO_SECTIONS.map((section) => section.id)).toEqual([
      "studio",
      "workflows",
      "posting",
      "automation",
    ]);
    expect(text).toMatch(/Start from the original/);
    expect(text).toMatch(/do not run a finished copy/i);
    expect(text).toMatch(/Drive in, Drive out/);
    expect(text).toMatch(/do not drop every copy on every account at the same time/i);
    expect(text).toMatch(/Trial Reels/);
    expect(text).toMatch(/sexual clips/);
    expect(text).toMatch(/Repurpose\.io or Buffer/);
    expect(text).not.toMatch(/Reconstruct first/i);
    expect(text).not.toMatch(/Convert only/i);
    expect(text).not.toMatch(/What this is not/i);
    expect(text).not.toMatch(/count as pass/i);
  });

  it("does not publish fingerprint internals", () => {
    const text = howToPlainText();
    for (const pattern of HOW_TO_FORBIDDEN) {
      expect(text).not.toMatch(pattern);
    }
  });
});
