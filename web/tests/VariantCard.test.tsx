import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { VariantCard } from "@/components/gallery/VariantCard";
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
    uniqueness: 0.5,
    uniqueness_status: "ok",
    uniqueness_target: 32 / 64,
    escalated: false,
    ...over,
  };
}

describe("VariantCard uniqueness", () => {
  it("shows uniqueness percent (higher = more different)", () => {
    render(
      <VariantCard
        variant={variant()}
        sourceId="s1"
        onOpen={() => {}}
        selected={false}
        onToggle={() => {}}
      />,
    );
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.queryByText("esc")).not.toBeInTheDocument();
  });

  it("shows an esc badge next to uniqueness when escalated", () => {
    render(
      <VariantCard
        variant={variant({ escalated: true })}
        sourceId="s1"
        onOpen={() => {}}
        selected={false}
        onToggle={() => {}}
      />,
    );
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText("esc")).toBeInTheDocument();
  });
});
