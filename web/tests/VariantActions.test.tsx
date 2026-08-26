import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { VariantOut } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  regenerate: vi.fn().mockResolvedValue(undefined),
  setPlatformResult: vi.fn().mockResolvedValue({}),
  setPostUrl: vi.fn().mockResolvedValue({}),
}));

import { setPlatformResult } from "@/lib/api";
import { VariantActions } from "@/components/variant/VariantActions";
import { clearSharedVariantFileCache } from "@/lib/shareVideos";

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

afterEach(() => {
  clearSharedVariantFileCache();
  Reflect.deleteProperty(navigator, "canShare");
  Reflect.deleteProperty(navigator, "share");
});

describe("VariantActions customer actions", () => {
  it("keeps duplicate rejected and download, without pass/flag/manifest", () => {
    render(<VariantActions sourceId="s1" variant={variant()} onRegenerate={() => {}} />);
    expect(screen.getByRole("button", { name: /Duplicate rejected/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Download/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Passed upload/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Flagged/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /View manifest/ })).not.toBeInTheDocument();
    expect(screen.getByText(/unlabeled = pass/i)).toBeInTheDocument();
    expect(screen.queryByTestId("platform-result-badge")).not.toBeInTheDocument();
  });

  it("does not show Flagged or Passed badges", () => {
    const { rerender } = render(
      <VariantActions
        sourceId="s1"
        variant={variant({ platform_result: "flagged" })}
        onRegenerate={() => {}}
      />,
    );
    expect(screen.queryByTestId("platform-result-badge")).not.toBeInTheDocument();
    expect(screen.queryByText(/Flagged/)).not.toBeInTheDocument();
    rerender(
      <VariantActions
        sourceId="s1"
        variant={variant({ platform_result: "passed" })}
        onRegenerate={() => {}}
      />,
    );
    expect(screen.queryByTestId("platform-result-badge")).not.toBeInTheDocument();
    expect(screen.queryByText(/Passed upload/)).not.toBeInTheDocument();
  });

  it("saves duplicate_reject on the variant", async () => {
    const onRegenerate = vi.fn();
    render(<VariantActions sourceId="s1" variant={variant()} onRegenerate={onRegenerate} />);
    fireEvent.click(screen.getByRole("button", { name: /Duplicate rejected/ }));
    await waitFor(() => {
      expect(setPlatformResult).toHaveBeenCalledWith("s1", 1, "duplicate_reject");
    });
    await waitFor(() => {
      expect(onRegenerate).toHaveBeenCalled();
    });
  });

  it("labels Save to Photos when the share sheet can take the clip", () => {
    Object.defineProperty(navigator, "canShare", {
      configurable: true,
      value: () => true,
    });
    render(<VariantActions sourceId="s1" variant={variant()} onRegenerate={() => {}} />);
    expect(screen.getByRole("button", { name: /save to photos/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Download/ })).not.toBeInTheDocument();
  });
});
