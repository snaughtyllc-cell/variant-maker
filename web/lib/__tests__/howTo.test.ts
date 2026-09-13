import { describe, expect, it } from "vitest";
import { HOW_TO_FORBIDDEN, HOW_TO_SECTIONS, howToPlainText } from "../howTo";

describe("howTo copy", () => {
  it("covers the operator loop, cadence, and ledger wording", () => {
    const text = howToPlainText();
    expect(HOW_TO_SECTIONS.map((section) => section.id)).toEqual([
      "source",
      "fast",
      "look",
      "handoff",
      "cadence",
      "ledger",
      "not",
    ]);
    expect(text).toMatch(/do not run a finished copy/i);
    expect(text).toMatch(/Reconstruct first \(HQ\)/);
    expect(text).toMatch(/off by default/);
    expect(text).toMatch(/do not dump a whole pack/i);
    expect(text).toMatch(/Unlabeled is unknown/i);
    expect(text).toMatch(/not a pass/i);
    expect(text).toMatch(/look-close/i);
    expect(text).not.toMatch(/count as pass/i);
  });

  it("does not publish fingerprint internals", () => {
    const text = howToPlainText();
    for (const pattern of HOW_TO_FORBIDDEN) {
      expect(text, String(pattern)).not.toMatch(pattern);
    }
  });
});
