import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GalleryToolbar } from "@/components/gallery/GalleryToolbar";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

describe("GalleryToolbar drops chips", () => {
  it("links Sent to Drive and Flagged this week into the drops board", () => {
    render(
      <GalleryToolbar
        count={0}
        variantCount={0}
        filterMode="all"
        onFilter={() => undefined}
        sort="newest"
        onSort={() => undefined}
        selectedCount={0}
        sendDisabledReason="none selected"
        onSend={() => undefined}
        selectAllLabel="Select all"
        onSelectAll={() => undefined}
      />,
    );
    expect(screen.getByRole("link", { name: "Sent to Drive" })).toHaveAttribute("href", "/drops");
    expect(screen.getByRole("link", { name: "Flagged this week" })).toHaveAttribute(
      "href",
      "/drops?filter=flagged_week",
    );
  });
});
