import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { DrivePickerModal } from "@/components/studio/DrivePickerModal";
import type { Destination, DriveStatus } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  getDriveStatus: vi.fn(),
  listDestinations: vi.fn(),
  listDestinationVideos: vi.fn(),
  createDestination: vi.fn(),
}));

import { createDestination, getDriveStatus, listDestinationVideos, listDestinations } from "@/lib/api";

const ready: DriveStatus = {
  status: "ready",
  sa_email: null,
  message: "Drive ready",
  auth_mode: "oauth",
  connected_email: "studio@varimo.io",
  oauth_available: true,
  share_email: "studio@varimo.io",
};

const created: Destination = {
  id: "dst_jaden",
  name: "Jaden Reels",
  folder_id: "1Xr5BFioBkYJuGFyuXkUIUl6ynpYqvcOj",
  auth_mode: "oauth",
};

describe("DrivePickerModal paste", () => {
  beforeEach(() => {
    vi.mocked(getDriveStatus).mockResolvedValue(ready);
    vi.mocked(listDestinations).mockResolvedValue([]);
    vi.mocked(listDestinationVideos).mockResolvedValue({ videos: [] });
    vi.mocked(createDestination).mockReset();
  });

  it("lets an invited operator paste a folder link when no destinations exist", async () => {
    vi.mocked(createDestination).mockResolvedValue(created);
    render(
      <DrivePickerModal existingDestinationId={null} onConfirm={() => {}} onClose={() => {}} />,
    );
    const url = await screen.findByPlaceholderText(/paste drive folder link/i);
    expect(url).toBeEnabled();
    fireEvent.change(screen.getByPlaceholderText("Name"), { target: { value: "Jaden Reels" } });
    fireEvent.change(url, {
      target: { value: "https://drive.google.com/drive/folders/1Xr5BFioBkYJuGFyuXkUIUl6ynpYqvcOj" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    await waitFor(() => {
      expect(createDestination).toHaveBeenCalledWith(
        "Jaden Reels",
        "https://drive.google.com/drive/folders/1Xr5BFioBkYJuGFyuXkUIUl6ynpYqvcOj",
      );
    });
    expect(await screen.findByText("Jaden Reels")).toBeTruthy();
  });
});
