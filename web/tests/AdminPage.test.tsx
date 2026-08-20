import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { AdminWorkspace, AuthMe, Invite } from "@/lib/types";

const push = vi.fn();
const replace = vi.fn();

const me: { data: AuthMe | undefined; isLoading: boolean; mutate: ReturnType<typeof vi.fn> } = {
  data: undefined,
  isLoading: false,
  mutate: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
}));

vi.mock("@/lib/useAuthMe", () => ({
  useAuthMe: () => me,
}));

vi.mock("@/lib/api", () => ({
  listAdminWorkspaces: vi.fn(),
  listInvites: vi.fn(),
  createInvite: vi.fn(),
  deleteInvite: vi.fn(),
  setAdminView: vi.fn(),
}));

import {
  listAdminWorkspaces,
  listInvites,
  setAdminView,
} from "@/lib/api";
import AdminPage from "@/app/admin/page";

const ADMIN: AuthMe = {
  auth_required: true,
  email: "jeff@example.com",
  name: "Jeff",
  workspace_id: "ws_home",
  workspace_name: "Jeff",
  home_workspace_id: "ws_home",
  viewing_other: false,
  role: "owner",
  is_admin: true,
};

const workspaces: AdminWorkspace[] = [
  {
    id: "ws_va",
    name: "Maya",
    owner_email: "maya@example.com",
    member_count: 2,
    running: 1,
    fast: 1,
    hq: 0,
    last_job_utc: "2026-08-20T00:00:00Z",
    last_error: null,
  },
];

const invites: Invite[] = [];

beforeEach(() => {
  push.mockReset();
  replace.mockReset();
  me.data = ADMIN;
  me.isLoading = false;
  me.mutate.mockReset();
  me.mutate.mockResolvedValue(undefined);
  vi.mocked(listAdminWorkspaces).mockResolvedValue(workspaces);
  vi.mocked(listInvites).mockResolvedValue(invites);
  vi.mocked(setAdminView).mockResolvedValue(undefined);
});

describe("Admin page", () => {
  it("lists workspaces and Open switches view then goes home", async () => {
    render(<AdminPage />);
    expect(await screen.findByText("Maya")).toBeInTheDocument();
    expect(screen.getByText("maya@example.com")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^open$/i }));
    await waitFor(() => {
      expect(setAdminView).toHaveBeenCalledWith("ws_va");
    });
    expect(push).toHaveBeenCalledWith("/");
  });

  it("sends non-admins home", async () => {
    me.data = { ...ADMIN, is_admin: false };
    render(<AdminPage />);
    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith("/");
    });
  });
});
