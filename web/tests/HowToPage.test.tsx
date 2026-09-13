import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HowToPage } from "@/components/help/HowToPage";
import { HOW_TO_FORBIDDEN } from "@/lib/howTo";

describe("HowToPage", () => {
  it("renders case scenarios and jump links", () => {
    render(<HowToPage />);
    expect(screen.getByRole("heading", { level: 1, name: "How to" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /studio → gallery/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^workflows$/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^posting$/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^automation$/i })).toBeInTheDocument();
    expect(screen.getByText(/Start from the original/)).toBeInTheDocument();
    expect(screen.getByText(/Trial Reels/)).toBeInTheDocument();
    expect(screen.queryByText(/Reconstruct first/)).not.toBeInTheDocument();
    expect(screen.queryByText(/What this is not/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Studio" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Gallery" })).toHaveAttribute("href", "/gallery");
    expect(screen.getByRole("link", { name: "Workflows" })).toHaveAttribute("href", "/workflows");
    expect(screen.getByRole("link", { name: "Drive" })).toHaveAttribute("href", "/settings/drive");
    expect(screen.queryByRole("link", { name: "Drops" })).not.toBeInTheDocument();
  });

  it("does not publish fingerprint internals on the page", () => {
    render(<HowToPage />);
    const shown = document.body.textContent || "";
    for (const pattern of HOW_TO_FORBIDDEN) {
      expect(shown).not.toMatch(pattern);
    }
  });
});
