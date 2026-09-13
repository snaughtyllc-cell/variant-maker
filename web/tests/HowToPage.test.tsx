import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HowToPage } from "@/components/help/HowToPage";
import { HOW_TO_FORBIDDEN } from "@/lib/howTo";

describe("HowToPage", () => {
  it("renders the operator loop and jump links", () => {
    render(<HowToPage />);
    expect(screen.getByRole("heading", { level: 1, name: "How to" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /start from the original/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /make a fast pack/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /label what happened/i })).toBeInTheDocument();
    expect(screen.getByText(/Reconstruct first \(HQ\)/)).toBeInTheDocument();
    expect(screen.getByText(/Unlabeled is unknown/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Studio" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Gallery" })).toHaveAttribute("href", "/gallery");
    expect(screen.getByRole("link", { name: "Drive" })).toHaveAttribute("href", "/settings/drive");
    expect(screen.getByRole("link", { name: "Drops" })).toHaveAttribute("href", "/drops");
    expect(screen.getByRole("link", { name: "Workflows" })).toHaveAttribute("href", "/workflows");
  });

  it("does not publish fingerprint internals on the page", () => {
    render(<HowToPage />);
    const shown = document.body.textContent || "";
    for (const pattern of HOW_TO_FORBIDDEN) {
      expect(shown, String(pattern)).not.toMatch(pattern);
    }
  });
});
