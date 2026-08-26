import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { GenerateButton } from "@/components/studio/GenerateButton";

describe("GenerateButton", () => {
  it("labels Generate when idle", () => {
    render(<GenerateButton fileCount={1} perVideo={20} onClick={vi.fn()} />);
    const btn = screen.getByRole("button");
    expect(btn).toHaveTextContent("Generate");
    expect(btn).not.toHaveTextContent("Generate another");
    expect(btn).not.toHaveAttribute("data-complete");
    expect(btn).toHaveClass("studio-generate-button");
  });

  it("labels Generate another when the last run is complete", () => {
    render(
      <GenerateButton
        fileCount={1}
        perVideo={20}
        onClick={vi.fn()}
        jobId="j1"
        complete
      />,
    );
    const btn = screen.getByRole("button");
    expect(btn).toHaveTextContent("Generate another");
    expect(btn).toHaveAttribute("data-complete", "true");
    expect(screen.getByText(/new pack/i)).toBeInTheDocument();
    expect(btn).not.toBeDisabled();
  });

  it("labels Generating while a job is in progress", () => {
    render(
      <GenerateButton
        fileCount={1}
        perVideo={20}
        onClick={vi.fn()}
        jobId="j1"
        complete={false}
        disabled
      />,
    );
    const btn = screen.getByRole("button");
    expect(btn).toHaveTextContent("Generating…");
    expect(btn).toBeDisabled();
    expect(btn).not.toHaveAttribute("data-complete");
  });
});
