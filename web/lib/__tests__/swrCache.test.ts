import { describe, expect, it } from "vitest";
import { PAGE_SWR } from "@/lib/swrCache";

describe("PAGE_SWR", () => {
  it("does not refetch just because the phone tab regained focus", () => {
    expect(PAGE_SWR.revalidateOnFocus).toBe(false);
    expect(PAGE_SWR.dedupingInterval).toBeGreaterThanOrEqual(10_000);
    expect(PAGE_SWR.keepPreviousData).toBe(true);
  });
});
