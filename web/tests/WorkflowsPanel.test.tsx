import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { Destination, DriveStatus, Workflow } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  getDriveStatus: vi.fn(),
  listDestinations: vi.fn(),
  listWorkflows: vi.fn(),
  listCaptionBanks: vi.fn(),
  createWorkflow: vi.fn(),
  deleteWorkflow: vi.fn(),
  runWorkflow: vi.fn(),
  updateWorkflow: vi.fn(),
  cancelWorkflow: vi.fn(),
}));

import {
  cancelWorkflow,
  getDriveStatus,
  listCaptionBanks,
  listDestinations,
  listWorkflows,
} from "@/lib/api";
import { WorkflowsPanel } from "@/components/workflows/WorkflowsPanel";

const status: DriveStatus = {
  status: "ready",
  sa_email: "bot@x.com",
  message: "Drive connected",
};

const destinations: Destination[] = [
  { id: "dst_in", name: "Inbox", folder_id: "IN", auth_mode: "oauth" },
  { id: "dst_out", name: "Out", folder_id: "OUT", auth_mode: "oauth" },
];

const live: Workflow = {
  id: "wf_1",
  name: "Strata Test",
  inbox_destination_id: "dst_in",
  output_destination_id: "dst_out",
  count: 8,
  quality_mode: "fast",
  allow_creative_escalate: true,
  enabled: true,
  poll_seconds: 240,
  last_sweep_at: "2026-08-20T14:00:00Z",
  last_summary: {
    queued: 1,
    exported: 0,
    skipped: 0,
    failed: 0,
    running: 1,
    job_ids: ["job_live"],
  },
  auto_caption: false,
  caption_bank_id: null,
};

beforeEach(() => {
  vi.mocked(getDriveStatus).mockResolvedValue(status);
  vi.mocked(listDestinations).mockResolvedValue(destinations);
  vi.mocked(listWorkflows).mockResolvedValue([live]);
  vi.mocked(listCaptionBanks).mockResolvedValue([]);
  vi.mocked(cancelWorkflow).mockResolvedValue({ ...live, enabled: false, last_summary: { ...live.last_summary!, running: 0 } });
});

describe("WorkflowsPanel cancel", () => {
  it("cancels a live sweep: Watch off + stop the pack", async () => {
    render(<WorkflowsPanel />);
    const cancel = await screen.findByRole("button", { name: /^cancel$/i });
    fireEvent.click(cancel);
    await waitFor(() => {
      expect(cancelWorkflow).toHaveBeenCalledWith("wf_1");
    });
  });
});
