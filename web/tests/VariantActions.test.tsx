import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { VariantActions } from "@/components/variant/VariantActions";
import type { VariantOut } from "@/lib/types";

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
    file_url: "/files/v01.mp4",
    platform_result: null,
    ...over,
  };
}

describe("VariantActions platform labels", () => {
  it("offers Flagged alongside Passed and Duplicate rejected", () => {
    render(<VariantActions sourceId="s1" variant={variant()} onRegenerate={() => {}} />);
    expect(screen.getByRole("button", { name: /Passed upload/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Duplicate rejected/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Flagged/ })).toBeInTheDocument();
    expect(screen.getByText(/unlabeled = pass/i)).toBeInTheDocument();
    expect(screen.queryByTestId("platform-result-badge")).not.toBeInTheDocument();
  });

  it("shows a Flagged badge when already labeled", () => {
    render(
      <VariantActions
        sourceId="s1"
        variant={variant({ platform_result: "flagged" })}
        onRegenerate={() => {}}
      />,
    );
    expect(screen.getByTestId("platform-result-badge")).toHaveTextContent("⚑ Flagged");
  });
});
