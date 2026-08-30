import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { AuthMe } from "@/lib/types";

const me: { data: AuthMe | undefined; isLoading: boolean } = {
  data: undefined,
  isLoading: false,
};

vi.mock("@/lib/useAuthMe", () => ({
  useAuthMe: () => me,
}));

vi.mock("@/lib/runStore", () => ({
  useRun: () => ({
    start: vi.fn(),
    beginPrepare: vi.fn(),
    clear: vi.fn(),
    jobId: null,
    complete: false,
    sources: [],
    progress: { sources: [], complete: true },
    qualityMode: "fast",
  }),
}));

vi.mock("@/lib/useQueue", () => ({
  useQueue: () => ({
    data: { running: 0, fast: 0, hq: 0, jobs: [] },
    mutate: vi.fn(),
    isLoading: false,
  }),
}));

vi.mock("@/lib/api", () => ({
  createJob: vi.fn(),
  createJobFromDrive: vi.fn(),
  cancelJob: vi.fn(),
}));

import StudioPage from "@/app/page";

const SOLO: AuthMe = {
  auth_required: true,
  email: "solo@example.com",
  name: "Solo",
  workspace_id: "ws_solo",
  workspace_name: "Solo",
  home_workspace_id: "ws_solo",
  viewing_other: false,
  role: "owner",
  is_admin: false,
  has_password: true,
  experience: "solo",
};

const AGENCY: AuthMe = {
  ...SOLO,
  email: "ops@example.com",
  name: "Ops",
  workspace_id: "ws_ops",
  workspace_name: "Ops studio",
  home_workspace_id: "ws_ops",
  experience: "agency",
};

beforeEach(() => {
  me.data = SOLO;
  me.isLoading = false;
});

describe("Studio page captions section", () => {
  it("shows Write captions for these copies before Generate for solo creators", () => {
    render(<StudioPage />);
    const captions = screen.getByRole("region", { name: /3 · captions/i });
    const generate = screen.getByRole("button", { name: /generate/i });
    expect(captions.compareDocumentPosition(generate) & Node.DOCUMENT_POSITION_FOLLOWING).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
    expect(screen.getByRole("checkbox", { name: /write captions for these copies/i })).toBeChecked();
    expect(screen.queryByText("Advanced")).not.toBeInTheDocument();
  });

  it("keeps the captions section when Advanced is visible for agency", () => {
    me.data = AGENCY;
    render(<StudioPage />);
    expect(screen.getByRole("region", { name: /3 · captions/i })).toBeInTheDocument();
    expect(screen.getByText("Advanced")).toBeInTheDocument();
  });

  it("styles the captions card like the variants stepper so it cannot collapse off the cockpit", () => {
    const css = readFileSync(resolve(__dirname, "../app/globals.css"), "utf8");
    expect(css).toMatch(/\.studio-setup\s*\{[^}]*display:\s*flex/s);
    expect(css).toMatch(/\.studio-caption-section\s*\{[^}]*background:/s);
    expect(css).not.toMatch(/\.studio-caption-section\s*\{[^}]*display:\s*none/s);
  });
});
