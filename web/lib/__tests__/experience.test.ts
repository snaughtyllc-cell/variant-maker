import { describe, expect, it } from "vitest";
import { isAgencyExperience, normalizeExperience } from "@/lib/experience";

describe("workspace experience", () => {
  it("treats missing as agency so current operator studios stay full", () => {
    expect(normalizeExperience(undefined)).toBe("agency");
    expect(isAgencyExperience({ experience: "solo" })).toBe(false);
    expect(isAgencyExperience({ experience: "solo", is_admin: true })).toBe(true);
    expect(isAgencyExperience({ auth_required: false, experience: "solo" })).toBe(true);
  });
});
