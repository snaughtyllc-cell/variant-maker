import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { VariantOut } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  regenerate: vi.fn().mockResolvedValue(undefined),
  setPlatformResult: vi.fn().mockResolvedValue({}),
  setPostUrl: vi.fn().mockResolvedValue({}),
}));

import { setPlatformResult } from "@/lib/api";
import { VariantActions } from "@/components/variant/VariantActions";

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

beforeEach(() => {
  vi.mocked(setPlatformResult).mockReset();
  vi.mocked(setPlatformResult).mockResolvedValue({} as VariantOut);
});

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

  it("saves Flagged on the variant (and Drop Ledger)", async () => {
    const onRegenerate = vi.fn();
    render(<VariantActions sourceId="s1" variant={variant()} onRegenerate={onRegenerate} />);
    fireEvent.click(screen.getByRole("button", { name: /Flagged/ }));
    await waitFor(() => {
      expect(setPlatformResult).toHaveBeenCalledWith("s1", 1, "flagged");
    });
    await waitFor(() => {
      expect(onRegenerate).toHaveBeenCalled();
    });
  });
});
