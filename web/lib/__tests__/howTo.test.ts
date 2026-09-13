import { describe, expect, it } from "vitest";
import { HOW_TO_CATEGORIES, HOW_TO_FORBIDDEN, howToPlainText } from "../howTo";

describe("howTo copy", () => {
  it("is three categories: Generating, Automation, Posting", () => {
    const text = howToPlainText();
    expect(HOW_TO_CATEGORIES.map((category) => category.id)).toEqual([
      "generating",
      "automation",
      "posting",
    ]);
    expect(text).toMatch(/Start from the original/);
    expect(text).toMatch(/do not run a finished copy/i);
    expect(text).toMatch(/Drive in, Drive out/);
    expect(text).toMatch(/Auto captions/);
    expect(text).toMatch(/caption bank/);
    expect(text).toMatch(/Plugins/);
    expect(text).toMatch(/Repurpose\.io or Buffer/);
    expect(text).toMatch(/do not drop every copy on every account at the same time/i);
    expect(text).toMatch(/Trial Reels/);
    expect(text).toMatch(/sexual clips/);
    expect(text).not.toMatch(/Analytics/i);
    expect(text).not.toMatch(/tester/i);
    expect(text).not.toMatch(/Reconstruct first/i);
    expect(text).not.toMatch(/Convert only/i);
    expect(text).not.toMatch(/What this is not/i);
  });

  it("does not publish fingerprint internals", () => {
    const text = howToPlainText();
    for (const pattern of HOW_TO_FORBIDDEN) {
      expect(text).not.toMatch(pattern);
    }
  });
});
