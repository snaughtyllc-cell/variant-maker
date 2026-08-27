import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GalleryToolbar } from "@/components/gallery/GalleryToolbar";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

const toolbarProps = {
  count: 0,
  variantCount: 0,
  filterMode: "all" as const,
  onFilter: () => undefined,
  sort: "newest" as const,
  onSort: () => undefined,
  selectAllLabel: "Select all",
  onSelectAll: () => undefined,
};

describe("GalleryToolbar drops chips", () => {
  it("links Sent to Drive and Flagged this week into the drops board", () => {
    render(<GalleryToolbar {...toolbarProps} />);
    expect(screen.getByRole("link", { name: "Sent to Drive" })).toHaveAttribute("href", "/drops");
    expect(screen.getByRole("link", { name: "Flagged this week" })).toHaveAttribute(
      "href",
      "/drops?filter=flagged_week",
    );
  });
});

describe("GalleryToolbar select all", () => {
  it("keeps Select all and leaves Save and Send on each pack", () => {
    render(<GalleryToolbar {...toolbarProps} />);
    expect(screen.getByRole("button", { name: /select all/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /select all \( /i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /save to phone/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /save to photos/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /send to drive/i })).not.toBeInTheDocument();
  });
});
