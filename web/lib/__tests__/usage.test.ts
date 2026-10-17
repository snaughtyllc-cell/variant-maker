import { describe, expect, it } from "vitest";
import { memberWeekCopy, sidebarUsage } from "@/lib/usage";

describe("memberWeekCopy", () => {
  it("says no packs when the operator has not generated this week", () => {
    expect(memberWeekCopy({})).toBe("This week: no packs");
    expect(memberWeekCopy({ week_fast: 0, week_hq: 0, week_packs: 0 })).toBe(
      "This week: no packs",
    );
  });

  it("shows Fast, HQ reconstructs, and pack count", () => {
    expect(
      memberWeekCopy({ week_fast: 5, week_hq: 1, week_packs: 2 }),
    ).toBe("This week: 5 Fast · 1 HQ · 2 packs");
    expect(
      memberWeekCopy({ week_fast: 3, week_hq: 0, week_packs: 1 }),
    ).toBe("This week: 3 Fast · 0 HQ · 1 pack");
  });
});

describe("sidebarUsage", () => {
  it("drains Agency Fast hours and flips to Usage after the included block", () => {
    expect(sidebarUsage(null)).toBeNull();
    expect(sidebarUsage({ uncapped: true, tone: "included", remaining_pct: 100 })).toBeNull();
    expect(
      sidebarUsage({
        uncapped: false,
        tone: "included",
        remaining_pct: 100,
        meter_line: "90 of 90h left",
      }),
    ).toEqual({ pct: 100, label: "90 of 90h left", tone: "included" });
    expect(
      sidebarUsage({
        uncapped: false,
        tone: "included",
        remaining_pct: 0,
        meter_line: "0 of 90h left",
      }),
    ).toEqual({ pct: 0, label: "0 of 90h left", tone: "included" });
    expect(
      sidebarUsage({
        uncapped: false,
        tone: "usage",
        remaining_pct: 0,
        meter_line: "Usage",
      }),
    ).toEqual({ pct: 0, label: "Usage", tone: "usage" });
  });
});
