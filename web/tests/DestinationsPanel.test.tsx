import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { DestinationsPanel } from "@/components/drive/DestinationsPanel";

vi.mock("@/lib/api", () => ({
  getDriveStatus: vi.fn(),
  listDestinations: vi.fn(),
  createDestination: vi.fn(),
  deleteDestination: vi.fn(),
  disconnectDriveOAuth: vi.fn(),
  testDestination: vi.fn(),
  updateDestination: vi.fn(),
}));

import { getDriveStatus, listDestinations } from "@/lib/api";

describe("DestinationsPanel share email", () => {
  beforeEach(() => {
    vi.mocked(getDriveStatus).mockResolvedValue({
      status: "ready",
      sa_email: "bot@x.iam.gserviceaccount.com",
      message: "Drive ready",
      auth_mode: "oauth",
      connected_email: "snaughtyllc@gmail.com",
      oauth_available: true,
      share_email: "snaughtyllc@gmail.com",
    });
    vi.mocked(listDestinations).mockResolvedValue([]);
  });

  it("shows snaughtyllc@gmail.com as the Drive share email the team already uses", async () => {
    render(<DestinationsPanel />);
    await waitFor(() => {
      expect(screen.getByTestId("drive-share-email").textContent).toBe("snaughtyllc@gmail.com");
    });
    expect(screen.getByText(/Share this email/i)).toBeTruthy();
    expect(screen.getByText(/paste the folder link below/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Copy" })).toBeTruthy();
    expect(screen.queryByText(/Reconnect Google as/)).toBeNull();
  });
});
