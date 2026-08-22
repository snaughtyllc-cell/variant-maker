import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { AdvancedPanel } from "@/components/studio/AdvancedPanel";

const noop = () => {};

describe("AdvancedPanel output copy", () => {
  it("shows display-only Matches source, not a vertical-only dropdown", () => {
    render(
      <AdvancedPanel
        allowCreativeEscalate={false}
        onAllowCreativeEscalateChange={noop}
        qualityMode="fast"
        onQualityModeChange={noop}
      />,
    );
    expect(screen.getByText("Output: Matches source")).toBeInTheDocument();
    expect(screen.queryByText(/Vertical 1080/)).not.toBeInTheDocument();
    expect(screen.queryByText("▾")).not.toBeInTheDocument();
  });

  it("explains auto 9:16 and 16:9 canvases when opened", () => {
    render(
      <AdvancedPanel
        allowCreativeEscalate={false}
        onAllowCreativeEscalateChange={noop}
        qualityMode="fast"
        onQualityModeChange={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByText("Advanced"));
    expect(screen.getByText("Matches source")).toBeInTheDocument();
    expect(
      screen.getByText("Auto — 9:16 → 1080×1920, 16:9 → 1920×1080."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toHaveDisplayValue("Fast");
  });
});
