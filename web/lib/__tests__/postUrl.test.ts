import { describe, it, expect } from "vitest";
import {
  hostFromPostUrl,
  postLinkHint,
  postLinkOpenLabel,
  postedCountCopy,
} from "@/lib/postUrl";

describe("postUrl copy", () => {
  it("tells VAs to paste a live link because Studio does not post", () => {
    expect(postLinkHint()).toMatch(/paste the live/i);
    expect(postLinkHint()).toMatch(/does not post/i);
    expect(postLinkOpenLabel()).toBe("Open post");
  });

  it("counts saved permalinks on a pack", () => {
    expect(postedCountCopy(0)).toBeNull();
    expect(postedCountCopy(1)).toBe("1 live post");
    expect(postedCountCopy(3)).toBe("3 live posts");
  });

  it("shows a short host for the saved link", () => {
    expect(hostFromPostUrl("https://www.instagram.com/reel/AbC/")).toBe("instagram.com");
  });
});
