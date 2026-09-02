import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { AnalyticsBoard } from "../analytics/AnalyticsBoard";

const mockGetInstagramStatus = vi.fn();
const mockGetInstagramAnalytics = vi.fn();
const mockSyncInstagram = vi.fn();
const mockRegenerate = vi.fn();

vi.mock("@/lib/api", () => ({
  getInstagramStatus: () => mockGetInstagramStatus(),
  getInstagramAnalytics: () => mockGetInstagramAnalytics(),
  syncInstagram: () => mockSyncInstagram(),
  regenerate: (id: string, n: number) => mockRegenerate(id, n),
  disconnectInstagram: vi.fn(),
  pasteInstagramToken: vi.fn(),
}));

vi.mock("@/lib/useAuthMe", () => ({
  useAuthMe: () => ({ data: { auth_required: false, email: "ops@example.com" } }),
}));

describe("AnalyticsBoard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetInstagramStatus.mockResolvedValue({
      oauth_available: true,
      connected: true,
      message: "",
      accounts: [{ user_id: "1", username: "jeff", name: "Jeff" }],
    });
    mockGetInstagramAnalytics.mockResolvedValue({
      insights_views: 312400,
      insights_linked: 14,
      ranked: [
        {
          source_id: "winner",
          filename: "winner.mp4",
          insights_views: 300000,
          insights_linked: 12,
          insights_unknown: 8,
        },
        {
          source_id: "quiet",
          filename: "quiet.mp4",
          insights_views: 12400,
          insights_linked: 2,
          insights_unknown: 0,
        },
      ],
      accounts: [{ user_id: "1", username: "jeff", name: "Jeff" }],
    });
  });

  it("shows pack totals and ranked originals on the Analytics tab", async () => {
    render(<AnalyticsBoard />);
    expect(await screen.findByText(/312k views across 14 linked posts/i)).toBeTruthy();
    expect(screen.getByText(/Winner · winner.mp4/)).toBeTruthy();
    expect(screen.getByText("quiet.mp4")).toBeTruthy();
    expect(screen.getByRole("button", { name: /generate 20 more of this original/i })).toBeTruthy();
  });

  it("mints more of the winning original", async () => {
    mockRegenerate.mockResolvedValue({});
    render(<AnalyticsBoard />);
    fireEvent.click(await screen.findByRole("button", { name: /generate 20 more of this original/i }));
    expect(mockRegenerate).toHaveBeenCalledWith("winner", 20);
  });
});
