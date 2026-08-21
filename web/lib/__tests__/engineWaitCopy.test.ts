import { describe, it, expect } from "vitest";
import { ENGINE_WAIT_HEADING, ENGINE_WAIT_LINES } from "@/lib/engineWaitCopy";

describe("engineWaitCopy", () => {
  it("tells VAs a quiet first click is a wake-up, not a hang", () => {
    expect(ENGINE_WAIT_HEADING).toMatch(/engine wait/i);
    const blob = ENGINE_WAIT_LINES.join(" ");
    expect(blob).toMatch(/30 seconds|couple of minutes/i);
    expect(blob).toMatch(/not stuck/i);
    expect(blob).toMatch(/10 minutes/i);
    expect(blob).toMatch(/HQ is slower/i);
    expect(blob).toMatch(/several minutes/i);
    expect(blob).not.toMatch(/one minute/i);
  });
});
