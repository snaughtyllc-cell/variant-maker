import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ProgressPanel } from "@/components/studio/ProgressPanel";
import { initRun } from "@/lib/progress";

vi.mock("@/lib/runStore", () => ({
  useRun: () => ({
    jobId: "j1",
    progress: { ...initRun([{ source_id: "s1", filename: "a.mp4", requested: 8 }]), complete: true },
    complete: true,
    clear: vi.fn(),
    qualityMode: "fast",
  }),
}));

describe("ProgressPanel contrast", () => {
  it("keeps New run and done readable on the dark pane", () => {
    render(<ProgressPanel />);
    const neu = screen.getByRole("button", { name: "New run" });
    expect(neu.className).toMatch(/studio-progress-newrun/);
    const pill = screen.getByText("done");
    expect(pill.className).toMatch(/studio-progress-pill/);
  });
});
