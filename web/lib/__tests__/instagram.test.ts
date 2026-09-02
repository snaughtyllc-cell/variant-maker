import { describe, expect, it } from "vitest";
import {
  AMPLIFY_MORE_N,
  formatViews,
  galleryViewsCopy,
  handleLabel,
  igOauthErrorMessage,
  insightSnapshotCopy,
  packViewsCopy,
  variantViewsCopy,
} from "@/lib/instagram";

describe("formatViews", () => {
  it("keeps unknown as an em dash", () => {
    expect(formatViews(null)).toBe("—");
  });

  it("compacts thousands", () => {
    expect(formatViews(312400)).toBe("312k");
    expect(formatViews(1500)).toBe("1.5k");
  });
});

describe("packViewsCopy", () => {
  it("hides when nothing is linked", () => {
    expect(packViewsCopy(0, 0, 20)).toBeNull();
  });

  it("does not treat unlinked packs as zero views", () => {
    expect(packViewsCopy(312400, 14, 20)).toBe("312k views · 14 of 20 linked");
  });
});

describe("galleryViewsCopy", () => {
  it("asks to connect on the Analytics tab when no accounts", () => {
    expect(galleryViewsCopy(null, 0, 0)).toMatch(/Connect Instagram testers on Analytics/i);
  });
});

describe("variantViewsCopy", () => {
  it("hides unlinked copies instead of showing zero", () => {
    expect(variantViewsCopy(0, false)).toBeNull();
  });

  it("compacts linked views", () => {
    expect(variantViewsCopy(312400, true)).toBe("312k");
  });
});

describe("insightSnapshotCopy", () => {
  it("joins the Insights snapshot without inventing flagged", () => {
    expect(insightSnapshotCopy({ views: 1500, likes: 12 })).toBe("1.5k views · 12 likes");
    expect(insightSnapshotCopy({ views: 1500, likes: 12 })).not.toMatch(/flagged/i);
  });
});

describe("amplify count", () => {
  it("mints a Fast 20 of the winning original", () => {
    expect(AMPLIFY_MORE_N).toBe(20);
  });
});

describe("igOauthErrorMessage", () => {
  it("does not tell them to paste a Meta token", () => {
    expect(igOauthErrorMessage("exchange_failed")).not.toMatch(/paste/i);
  });
});

describe("handleLabel", () => {
  it("prefixes at", () => {
    expect(handleLabel("maya.main")).toBe("@maya.main");
  });
});
