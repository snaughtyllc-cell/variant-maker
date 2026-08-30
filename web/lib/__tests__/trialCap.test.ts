import { describe, expect, it } from "vitest";
import { copiesPerSourceMax, sourcesRemaining, usagePair, trialCapHint } from "@/lib/trialCap";
import { MAX_PER_VIDEO } from "@/lib/variantStepperCopy";
import type { AuthMe } from "@/lib/types";

const base: AuthMe = {
  auth_required: true,
  email: "t@x.com",
  name: "T",
  workspace_id: "ws",
  workspace_name: "T",
  home_workspace_id: "ws",
  viewing_other: false,
  role: "owner",
  is_admin: false,
  has_password: true,
};

describe("trialCap", () => {
  it("leaves admins and empty caps unlimited", () => {
    expect(copiesPerSourceMax({ ...base, is_admin: true, variants_per_source_limit: 3 })).toBe(
      MAX_PER_VIDEO,
    );
    expect(copiesPerSourceMax(base)).toBe(MAX_PER_VIDEO);
    expect(sourcesRemaining(base)).toBeNull();
    expect(sourcesRemaining({ ...base, is_admin: true, source_limit: 2, sources_used: 2 })).toBeNull();
  });

  it("clamps testers to the admin-set numbers", () => {
    expect(copiesPerSourceMax({ ...base, variants_per_source_limit: 8 })).toBe(8);
    expect(sourcesRemaining({ ...base, source_limit: 5, sources_used: 2 })).toBe(3);
    expect(sourcesRemaining({ ...base, source_limit: 5, sources_used: 9 })).toBe(0);
  });

  it("formats admin usage pairs", () => {
    expect(usagePair(0, 0)).toBe("—");
    expect(usagePair(3, 60)).toBe("3 src · 60");
  });

  it("writes a tester-facing trial hint", () => {
    expect(trialCapHint(base)).toBeNull();
    expect(trialCapHint({ ...base, is_admin: true, source_limit: 2 })).toBeNull();
    expect(trialCapHint({ ...base, source_limit: 5, sources_used: 2, variants_per_source_limit: 8 })).toBe(
      "3 source clips left on this trial. Max 8 copies per clip.",
    );
    expect(trialCapHint({ ...base, source_limit: 1, sources_used: 1 })).toBe(
      "This studio has used its source cap.",
    );
  });
});
