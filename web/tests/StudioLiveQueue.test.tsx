import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { initRun } from "@/lib/progress";

vi.mock("@/lib/useQueue", () => ({
  useQueue: () => ({
    data: { running: 0, fast: 0, hq: 0, jobs: [] },
    mutate: vi.fn(),
    isLoading: false,
  }),
}));

vi.mock("@/lib/runStore", () => ({
  useRun: () => ({
    jobId: null,
    progress: initRun([]),
    complete: false,
  }),
}));

import { StudioLiveQueue } from "@/components/studio/StudioLiveQueue";

describe("StudioLiveQueue reserved tracks", () => {
  it("keeps the rows track mounted when the queue is empty so Generate cannot grow the rail", () => {
    const { container } = render(<StudioLiveQueue />);
    expect(container.querySelector(".studio-live__rows")).toBeTruthy();
    expect(container.querySelector(".studio-live__finished")).toBeTruthy();
    expect(screen.getByText(/Queue is clear/i)).toBeInTheDocument();
  });
});
