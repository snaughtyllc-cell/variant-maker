import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { VariantOut } from "@/lib/types";

const setPostUrl = vi.fn();

vi.mock("@/lib/api", () => ({
  setPostUrl: (...args: unknown[]) => setPostUrl(...args),
}));

import { PostLinkField } from "@/components/variant/PostLinkField";
import { postLinkHint, postLinkOpenLabel, postLinkSaveLabel } from "@/lib/postUrl";

function variant(over: Partial<VariantOut> = {}): VariantOut {
  return {
    index: 1,
    filename: "v01.mp4",
    status: "ok",
    quality: {
      vmaf: 95,
      histogram_ok: true,
      regen_count: 0,
      passed: true,
      spatial_vmaf: null,
      spatial_ok: null,
    },
    file_url: "/api/variants/s1/v01.mp4",
    ...over,
  };
}

describe("PostLinkField", () => {
  beforeEach(() => {
    setPostUrl.mockReset();
    setPostUrl.mockResolvedValue({ ...variant(), post_url: "https://www.instagram.com/reel/AbC/" });
  });

  it("explains paste-the-link tracking", () => {
    render(<PostLinkField sourceId="s1" variant={variant()} onSaved={() => {}} />);
    expect(screen.getByText(postLinkHint())).toBeInTheDocument();
    expect(screen.getByRole("button", { name: postLinkSaveLabel() })).toBeInTheDocument();
  });

  it("opens a saved permalink in a new tab", () => {
    render(
      <PostLinkField
        sourceId="s1"
        variant={variant({ post_url: "https://www.instagram.com/reel/AbC/" })}
        onSaved={() => {}}
      />,
    );
    const link = screen.getByRole("link", { name: new RegExp(postLinkOpenLabel(), "i") });
    expect(link).toHaveAttribute("href", "https://www.instagram.com/reel/AbC/");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("saves a pasted URL", async () => {
    const onSaved = vi.fn();
    render(<PostLinkField sourceId="s1" variant={variant()} onSaved={onSaved} />);
    fireEvent.change(screen.getByLabelText(/live post link/i), {
      target: { value: "https://www.tiktok.com/@va/video/1" },
    });
    fireEvent.click(screen.getByRole("button", { name: postLinkSaveLabel() }));
    await waitFor(() => {
      expect(setPostUrl).toHaveBeenCalledWith("s1", 1, "https://www.tiktok.com/@va/video/1");
    });
    expect(onSaved).toHaveBeenCalled();
  });
});
