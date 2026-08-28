import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { initRun, type RunProgress } from "@/lib/progress";

const queue = {
  data: { running: 0, fast: 0, hq: 0, jobs: [] as never[] },
  mutate: vi.fn(),
  isLoading: false,
};

const run: { jobId: string | null; complete: boolean; progress: RunProgress } = {
  jobId: null,
  complete: false,
  progress: initRun([]),
};

vi.mock("@/lib/useQueue", () => ({
  useQueue: () => queue,
}));

vi.mock("@/lib/runStore", () => ({
  useRun: () => run,
}));

vi.mock("@/lib/api", () => ({
  cancelJob: vi.fn(),
  sourceUrl: (id: string) => `/api/sources/${id}/source`,
}));

import { StudioLiveQueue } from "@/components/studio/StudioLiveQueue";

const quality = {
  vmaf: 96,
  histogram_ok: true,
  regen_count: 0,
  passed: true,
  spatial_vmaf: null,
  spatial_ok: null,
};

describe("StudioLiveQueue reserved tracks", () => {
  beforeEach(() => {
    run.jobId = null;
    run.complete = false;
    run.progress = initRun([]);
    queue.data = { running: 0, fast: 0, hq: 0, jobs: [] };
  });

  it("keeps the rows track mounted when the queue is empty so Generate cannot grow the rail", () => {
    const { container } = render(<StudioLiveQueue />);
    expect(container.querySelector(".studio-live__rows")).toBeTruthy();
    expect(container.querySelector(".studio-live__finished")).toBeTruthy();
    expect(screen.getByText(/Queue is clear/i)).toBeInTheDocument();
  });

  it("shows live copy tiles with a finished thumb and a render overlay", () => {
    run.jobId = "j1";
    run.progress = {
      complete: false,
      bySource: {
        s1: {
          source_id: "s1",
          filename: "clip.mp4",
          requested: 3,
          delivered: 1,
          done: 1,
          inFlights: { 2: { index: 2, state: "rendering", attempt: 0, max_attempts: 3 } },
          variants: [
            {
              index: 1,
              filename: "v01.mp4",
              status: "ok",
              quality,
              file_url: "/api/variants/s1/v01.mp4",
              uniqueness: 0.55,
            },
          ],
        },
      },
    };

    render(<StudioLiveQueue />);
    expect(screen.getByText("LIVE COPIES")).toBeInTheDocument();
    expect(document.querySelector('[data-tile="done"]')).toBeTruthy();
    expect(document.querySelector('[data-tile="live"]')).toBeTruthy();
    expect(document.querySelector('[data-tile="waiting"]')).toBeTruthy();
    expect(document.querySelector('[data-tile="done"] video')).toBeTruthy();
    expect(document.querySelector('[data-tile="live"] video')).toBeTruthy();
    expect(document.querySelector('[data-has-thumb="true"]')).toBeTruthy();
    expect(screen.getByText("rendering")).toBeInTheDocument();
    expect(screen.getByText("55%")).toBeInTheDocument();
  });
});
