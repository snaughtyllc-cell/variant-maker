import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SendToDriveModal } from "@/components/drive/SendToDriveModal";
import type { Destination, ExportVariantRef } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  listCaptionBanks: vi.fn(async () => []),
  previewCaptions: vi.fn(async () => ({ captions: [] })),
  createDriveExport: vi.fn(),
  createDriveExportSplit: vi.fn(),
  splitResultToJobs: vi.fn((result) => result.jobs.map((j: { id: string; dest: string }) => ({
    export_id: j.id,
    destination_id: j.dest,
    folder_id: "",
    state: "pending",
    created_utc: "",
    files: [],
  }))),
}));

import {
  createDriveExport,
  createDriveExportSplit,
} from "@/lib/api";

const destinations: Destination[] = [
  { id: "dst_main", name: "Maya / main", folder_id: "f1", auth_mode: "oauth" },
  { id: "dst_trial", name: "Maya / trial", folder_id: "f2", auth_mode: "oauth" },
  { id: "dst_growth", name: "Maya / growth", folder_id: "f3", auth_mode: "oauth" },
];

function refs(n: number): ExportVariantRef[] {
  return Array.from({ length: n }, (_, i) => ({ source_id: "s1", index: i + 1 }));
}

beforeEach(() => {
  vi.mocked(createDriveExport).mockReset();
  vi.mocked(createDriveExportSplit).mockReset();
});

describe("SendToDriveModal split pack", () => {
  it("lets you pick Main Trial Growth destinations and previews 7 / 7 / 6", async () => {
    render(
      <SendToDriveModal
        refs={refs(20)}
        destinations={destinations}
        jobId="j1"
        onClose={() => {}}
      />,
    );
    fireEvent.click(screen.getByLabelText(/split pack/i));
    expect(screen.getByLabelText(/^Main$/i)).toHaveValue("dst_main");
    expect(screen.getByLabelText(/^Trial$/i)).toHaveValue("dst_trial");
    expect(screen.getByLabelText(/^Growth$/i)).toHaveValue("dst_growth");
    expect(screen.getByLabelText(/^Main$/i).tagName).toBe("SELECT");
    expect(screen.getByText(/7 files · 1–7/)).toBeInTheDocument();
    expect(screen.getByText(/7 files · 8–14/)).toBeInTheDocument();
    expect(screen.getByText(/6 files · 15–20/)).toBeInTheDocument();
    expect(screen.getByText(/20 of 20 assigned/)).toBeInTheDocument();
  });

  it("does not require Growth — 2 dests rebalance to 10 / 10", async () => {
    render(
      <SendToDriveModal
        refs={refs(20)}
        destinations={destinations}
        jobId="j1"
        onClose={() => {}}
      />,
    );
    fireEvent.click(screen.getByLabelText(/split pack/i));
    fireEvent.change(screen.getByLabelText(/^Growth$/i), { target: { value: "" } });
    expect(screen.getByText(/10 files · 1–10/)).toBeInTheDocument();
    expect(screen.getByText(/11–20/)).toBeInTheDocument();
    expect(screen.getByText(/20 of 20 assigned/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /split send/i })).not.toBeDisabled();
  });

  it("one destination can take the whole pack", async () => {
    render(
      <SendToDriveModal
        refs={refs(20)}
        destinations={destinations}
        onClose={() => {}}
      />,
    );
    fireEvent.click(screen.getByLabelText(/split pack/i));
    fireEvent.change(screen.getByLabelText(/^Trial$/i), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText(/^Growth$/i), { target: { value: "" } });
    expect(screen.getByText(/20 files · 1–20/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /split send/i })).not.toBeDisabled();
  });

  it("blocks send when counts do not equal the selected total", async () => {
    render(
      <SendToDriveModal
        refs={refs(20)}
        destinations={destinations}
        onClose={() => {}}
      />,
    );
    fireEvent.click(screen.getByLabelText(/split pack/i));
    fireEvent.change(screen.getByLabelText(/Main count/i), { target: { value: "5" } });
    expect(screen.getByText(/18 of 20 assigned/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /split send/i })).toBeDisabled();
  });

  it("submits only filled destinations with counts", async () => {
    vi.mocked(createDriveExportSplit).mockResolvedValue({
      ok: true,
      jobs: [
        { id: "exp_a", dest: "dst_main", files: ["v01.mp4"], count: 7 },
        { id: "exp_b", dest: "dst_trial", files: ["v08.mp4"], count: 7 },
        { id: "exp_c", dest: "dst_growth", files: ["v15.mp4"], count: 6 },
      ],
      split: [[1, 2, 3, 4, 5, 6, 7], [8, 9, 10, 11, 12, 13, 14], [15, 16, 17, 18, 19, 20]],
    });
    render(
      <SendToDriveModal
        refs={refs(20)}
        destinations={destinations}
        jobId="j1"
        onClose={() => {}}
      />,
    );
    fireEvent.click(screen.getByLabelText(/split pack/i));
    fireEvent.click(screen.getByRole("button", { name: /split send/i }));
    await waitFor(() => {
      expect(createDriveExportSplit).toHaveBeenCalledTimes(1);
    });
    expect(createDriveExport).not.toHaveBeenCalled();
    const payload = vi.mocked(createDriveExportSplit).mock.calls[0][0];
    expect(payload.job_id).toBe("j1");
    expect(payload.selected).toHaveLength(20);
    expect(payload.destinations).toEqual([
      { destination_id: "dst_main", label: "main", count: 7 },
      { destination_id: "dst_trial", label: "trial", count: 7 },
      { destination_id: "dst_growth", label: "growth", count: 6 },
    ]);
  });

  it("keeps single-destination confirm on the original export path", async () => {
    vi.mocked(createDriveExport).mockResolvedValue({
      export_id: "exp_1",
      destination_id: "dst_main",
      folder_id: "f1",
      state: "pending",
      created_utc: "Z",
      files: [],
    });
    render(
      <SendToDriveModal
        refs={refs(2)}
        destinations={destinations}
        jobId="j1"
        onClose={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /confirm/i }));
    await waitFor(() => {
      expect(createDriveExport).toHaveBeenCalledTimes(1);
    });
    expect(createDriveExportSplit).not.toHaveBeenCalled();
  });
});
