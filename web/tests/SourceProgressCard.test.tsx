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
});
