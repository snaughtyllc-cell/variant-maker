import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SourceProgressCard } from "@/components/studio/SourceProgressCard";
import type { SourceProgress } from "@/lib/progress";

const base: SourceProgress = {
  source_id: "s1",
  filename: "clip.mp4",
  requested: 4,
  delivered: 0,
  done: 0,
  variants: [],
};

describe("SourceProgressCard in-flight slot", () => {
  it("keeps a 9:16 dashed slot while the variant aspect is unknown", () => {
    render(
      <SourceProgressCard
        source={{
          ...base,
          inFlight: { index: 1, state: "rendering", attempt: 0, max_attempts: 3 },
        }}
      />,
    );
    const slot = screen.getByText("render").parentElement as HTMLElement;
    expect(slot.style.aspectRatio).toBe("9 / 16");
  });

  it("shows source vs variant stills on looking", () => {
    render(
      <SourceProgressCard
        source={{
          ...base,
          inFlight: { index: 1, state: "looking", attempt: 0, max_attempts: 3 },
          lookPreview: {
            index: 1,
            src: "/api/look/s1/look_v01_src.jpg",
            var: "/api/look/s1/look_v01.jpg",
            status: "ok",
            mae: 12,
          },
        }}
      />,
    );
    expect(screen.getByText(/v01 looking/)).toBeTruthy();
    expect(screen.getByText(/Look ok/)).toBeTruthy();
    expect(screen.getByAltText("Source").getAttribute("src")).toBe("/api/look/s1/look_v01_src.jpg");
    expect(screen.getByAltText("Variant").getAttribute("src")).toBe("/api/look/s1/look_v01.jpg");
    expect(screen.getByText("look")).toBeTruthy();
  });

  it("labels a uniqueness miss as couldn't unique", () => {
    render(
      <SourceProgressCard
        source={{
          ...base,
          requested: 1,
          done: 1,
          variants: [{
            index: 1,
            filename: "v01.mp4",
            status: "uniqueness_fail",
            quality: {
              vmaf: 96,
              histogram_ok: true,
              regen_count: 0,
              passed: true,
              spatial_vmaf: null,
              spatial_ok: null,
            },
            file_url: "/api/variants/s1/v01.mp4",
            uniqueness: 18 / 64,
            uniqueness_status: "below_floor",
          }],
        }}
      />,
    );
    expect(screen.getByText("couldn't unique")).toBeTruthy();
    expect(screen.getByText("28%")).toBeTruthy();
  });
});
