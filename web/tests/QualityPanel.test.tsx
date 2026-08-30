import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { QualityPanel } from "@/components/variant/QualityPanel";
import { uniquenessCustomerLabel } from "@/lib/prepareCopy";

describe("QualityPanel", () => {
  it("shows an Originality meter and hides technical quality rows", () => {
    render(
      <QualityPanel
        uniqueness={0.5}
        uniquenessStatus="ok"
        bestEffort={false}
      />,
    );
    expect(screen.getByText(uniquenessCustomerLabel())).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.queryByText("Look")).not.toBeInTheDocument();
    expect(screen.queryByText(/Look fail/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/MAE/)).not.toBeInTheDocument();
    expect(screen.queryByText("VMAF")).not.toBeInTheDocument();
    expect(screen.queryByText("Spatial guard")).not.toBeInTheDocument();
    expect(screen.queryByText("Histogram")).not.toBeInTheDocument();
    expect(screen.queryByText("Re-rolls")).not.toBeInTheDocument();
    expect(screen.queryByText("Similarity")).not.toBeInTheDocument();
    expect(screen.queryByText("✗ fail")).not.toBeInTheDocument();
    expect(screen.queryByText(/stronger uniqueness pass/i)).not.toBeInTheDocument();
  });

  it("says pixel SSIM is scored and copy-id heads are not yet", () => {
    render(
      <QualityPanel uniqueness={0.5} uniquenessStatus="ok" bestEffort={false} />,
    );
    expect(screen.getByText(/Pixel difference vs the original \(3 frames\)/)).toBeInTheDocument();
    expect(screen.getByText(/Not a platform check/)).toBeInTheDocument();
    expect(screen.getByText("Pixel · scored")).toBeInTheDocument();
    expect(screen.getByText("Visual copy-id · not scored")).toBeInTheDocument();
    expect(screen.getByText("Audio · not scored")).toBeInTheDocument();
  });

  it("uses mild copy when a copy needed extra processing", () => {
    render(<QualityPanel uniqueness={0.4} uniquenessStatus="ok" bestEffort />);
    expect(screen.getByText("This copy needed extra processing.")).toBeInTheDocument();
    expect(screen.queryByText(/Best effort after 3 re-rolls/i)).not.toBeInTheDocument();
  });
});
