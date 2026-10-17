import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { DriveStatus } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  getDriveStatus: vi.fn(),
}));

import { getDriveStatus } from "@/lib/api";
import { DriveTopbar } from "@/components/drive/DriveTopbar";

const ready: DriveStatus = {
  status: "ready",
  sa_email: "ops@example.com",
  message: "Drive ready (Google OAuth)",
  auth_mode: "oauth",
  connected_email: "ops@example.com",
  oauth_available: true,
  share_email: "ops@example.com",
};

const notConfigured: DriveStatus = {
  status: "not_configured",
  sa_email: null,
  message: "Drive not connected — Connect Google in Settings",
  auth_mode: null,
  connected_email: null,
  oauth_available: true,
  share_email: "drive@varyforge.app",
};

beforeEach(() => {
  vi.mocked(getDriveStatus).mockReset();
});

describe("DriveTopbar", () => {
  it("does not claim Google is connected when Drive is not ready", async () => {
    vi.mocked(getDriveStatus).mockResolvedValue(notConfigured);
    render(<DriveTopbar />);
    await waitFor(() => {
      expect(screen.getByTestId("drive-topbar-status").textContent).toMatch(/not connected/i);
    });
    expect(screen.queryByRole("button", { name: /test all access/i })).toBeNull();
  });

  it("shows connected after Drive is ready", async () => {
    vi.mocked(getDriveStatus).mockResolvedValue(ready);
    render(<DriveTopbar />);
    await waitFor(() => {
      expect(screen.getByTestId("drive-topbar-status").textContent).toMatch(/^Google connected$/);
    });
  });
});
