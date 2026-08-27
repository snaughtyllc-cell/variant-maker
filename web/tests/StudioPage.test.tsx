import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { captionSeedLabel, captionToggleLabel } from "@/lib/prepareCopy";

const createJob = vi.fn();
const createJobFromDrive = vi.fn();
const run = {
  start: vi.fn(),
  beginPrepare: vi.fn(),
  clear: vi.fn(),
  jobId: null as string | null,
  complete: false,
};

vi.mock("@/lib/useAuthMe", () => ({
  useAuthMe: () => ({
    data: { experience: "solo", is_admin: false, auth_required: true },
  }),
}));

vi.mock("@/lib/useQueue", () => ({
  useQueue: () => ({
    data: { running: 0, fast: 0, hq: 0, jobs: [] },
    mutate: vi.fn(),
    isLoading: false,
  }),
}));

vi.mock("@/lib/runStore", () => ({
  useRun: () => run,
}));

vi.mock("@/lib/api", () => ({
  createJob: (...args: unknown[]) => createJob(...args),
  createJobFromDrive: (...args: unknown[]) => createJobFromDrive(...args),
}));

import StudioPage from "@/app/page";

describe("Studio caption seed", () => {
  beforeEach(() => {
    createJob.mockReset();
    createJobFromDrive.mockReset();
    run.start.mockReset();
    run.beginPrepare.mockReset();
    run.clear.mockReset();
    run.jobId = null;
    run.complete = false;
    createJob.mockResolvedValue({ job_id: "j1", sources: [] });
  });

  it("shows the original caption box when captions are on, hides it when off", () => {
    render(<StudioPage />);
    expect(screen.getByLabelText(captionSeedLabel())).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: captionToggleLabel() }));
    expect(screen.queryByLabelText(captionSeedLabel())).not.toBeInTheDocument();
  });

  it("sends the pasted caption with Generate", async () => {
    const { container } = render(<StudioPage />);
    const file = new File([new Uint8Array([1, 2, 3])], "boil.mp4", { type: "video/mp4" });
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText(captionSeedLabel()), {
      target: { value: "POV boil #reels" },
    });
    const generate = await waitFor(() => {
      const btn = screen.getByRole("button", { name: /^generate/i });
      expect(btn).toBeEnabled();
      return btn;
    });
    fireEvent.click(generate);
    await waitFor(() => expect(createJob).toHaveBeenCalled());
    expect(createJob).toHaveBeenCalledWith(
      [file],
      20,
      true,
      "fast",
      true,
      "POV boil #reels",
    );
  });
});
