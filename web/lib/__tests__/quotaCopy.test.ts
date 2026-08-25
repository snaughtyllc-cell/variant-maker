import { describe, it, expect } from "vitest";
import { quotaBlocksRun, quotaCaption } from "../quotaCopy";

const creator = {
  plan: "creator",
  window_days: 30,
  fast_used: 180,
  fast_limit: 200,
  fast_remaining: 20,
  hq_used: 0,
  hq_limit: 0,
  hq_remaining: 0,
};

describe("quotaCopy", () => {
  it("is silent when the workspace is uncapped", () => {
    expect(
      quotaCaption(
        { ...creator, fast_limit: null, fast_remaining: null, hq_limit: null, hq_remaining: null },
        "fast",
        20,
      ),
    ).toBeNull();
  });

  it("shows used / limit and this-run need", () => {
    expect(quotaCaption(creator, "fast", 20)).toBe(
      "Fast copies: 180 / 200 in the last 30 days. This run needs 20 (20 left).",
    );
    expect(quotaBlocksRun(creator, "fast", 20)).toBe(false);
    expect(quotaBlocksRun(creator, "fast", 21)).toBe(true);
  });

  it("blocks HQ when the plan limit is 0", () => {
    expect(quotaBlocksRun(creator, "hq", 1)).toBe(true);
  });
});
