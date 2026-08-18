import { describe, it, expect } from "vitest";
import { clipInset, clampTime } from "@/lib/media";
describe("media helpers", () => {
  it("clipInset maps percent to inset", () => {
    expect(clipInset(54)).toBe("inset(0 46% 0 0)");
    expect(clipInset(0)).toBe("inset(0 100% 0 0)");
  });
  it("clampTime clamps to [0,duration]", () => {
    expect(clampTime(-1, 10)).toBe(0);
    expect(clampTime(5, 10)).toBe(5);
    expect(clampTime(99, 10)).toBe(10);
    expect(clampTime(5, 0)).toBe(0);
  });
});
