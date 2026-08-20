import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { DriveStatus } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  createDestination: vi.fn(),
  deleteDestination: vi.fn(),
  disconnectDriveOAuth: vi.fn(),
  getDriveStatus: vi.fn(),
  listDestinations: vi.fn(),
  testDestination: vi.fn(),
  updateDestination: vi.fn(),
}));

import { getDriveStatus, listDestinations } from "@/lib/api";
import { DestinationsPanel } from "@/components/drive/DestinationsPanel";

const READY: DriveStatus = {
  status: "ready",
  sa_email: null,
  connected_email: "ops@example.com",
  auth_mode: "oauth",
  oauth_available: true,
  message: "Drive ready",
};

const NOT_CONNECTED: DriveStatus = {
  status: "not_configured",
  sa_email: null,
  connected_email: null,
  auth_mode: "oauth",
  oauth_available: true,
  message: "Drive not connected — Connect Google in Settings",
};

beforeEach(() => {
  vi.mocked(getDriveStatus).mockReset();
  vi.mocked(listDestinations).mockReset();
  vi.mocked(listDestinations).mockResolvedValue([]);
});

describe("DestinationsPanel empty copy", () => {
  it("says add a folder that Workflows and Send to Drive use", async () => {
    vi.mocked(getDriveStatus).mockResolvedValue(READY);
    render(<DestinationsPanel />);
    expect(await screen.findByText(/no destinations yet/i)).toBeInTheDocument();
    expect(screen.getByText(/Workflows and Send to Drive use it/i)).toBeInTheDocument();
  });

  it("connect state tells operators to add a destination folder", async () => {
    vi.mocked(getDriveStatus).mockResolvedValue(NOT_CONNECTED);
    render(<DestinationsPanel />);
    expect(
      await screen.findByText(/Connect Google, then add a destination folder/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Connect Google" })).toHaveAttribute(
      "href",
      "/api/drive/oauth/start",
    );
  });
});
