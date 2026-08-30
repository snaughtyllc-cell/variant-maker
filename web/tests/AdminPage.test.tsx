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
  removeAdminUser: vi.fn(),
  setWorkspaceExperience: vi.fn(),
  patchAdminWorkspace: vi.fn(),
}));

import {
  listAdminWorkspaces,
  listInvites,
  removeAdminUser,
  setAdminView,
  setWorkspaceExperience,
  patchAdminWorkspace,
  createInvite,
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
  has_password: false,
};

const workspaces: AdminWorkspace[] = [
  {
    id: "ws_va",
    name: "Maya",
    owner_email: "maya@example.com",
    member_count: 2,
    members: [
      { email: "maya@example.com", name: "Maya", role: "owner" },
      { email: "va@example.com", name: "VA", role: "member" },
    ],
    running: 1,
    fast: 1,
    hq: 0,
    last_job_utc: "2026-08-20T00:00:00Z",
    last_error: null,
    experience: "agency",
    week_sources: 2,
    week_copies: 16,
    month_sources: 5,
    month_copies: 40,
    all_sources: 2,
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
  vi.mocked(removeAdminUser).mockResolvedValue(undefined);
  vi.mocked(setWorkspaceExperience).mockResolvedValue({
    ...workspaces[0],
    experience: "solo",
  });
  vi.mocked(patchAdminWorkspace).mockImplementation(async (_id, body) => ({
    ...workspaces[0],
    ...body,
  }));
  vi.mocked(createInvite).mockImplementation(async (email, kind, caps) => ({
    id: "inv_1",
    email,
    kind,
    workspace_id: kind === "join" ? "ws_home" : null,
    created_utc: "2026-08-30T00:00:00Z",
    source_limit: caps?.source_limit ?? null,
    variants_per_source_limit: caps?.variants_per_source_limit ?? null,
  }));
});

describe("Admin page", () => {
  it("lists workspaces and Open switches view then goes home", async () => {
    render(<AdminPage />);
    expect(await screen.findByText("Maya")).toBeInTheDocument();
    expect(screen.getAllByText("maya@example.com").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: /^open$/i }));
    await waitFor(() => {
      expect(setAdminView).toHaveBeenCalledWith("ws_va");
    });
    expect(push).toHaveBeenCalledWith("/");
  });

  it("lists member emails and Remove revokes a VA", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(listAdminWorkspaces)
      .mockResolvedValueOnce(workspaces)
      .mockResolvedValueOnce([
        {
          ...workspaces[0],
          member_count: 1,
          members: [{ email: "maya@example.com", name: "Maya", role: "owner" }],
        },
      ]);
    render(<AdminPage />);
    expect(await screen.findByText("va@example.com")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove va@example.com" }));
    await waitFor(() => {
      expect(removeAdminUser).toHaveBeenCalledWith("va@example.com");
    });
    await waitFor(() => {
      expect(screen.queryByText("va@example.com")).not.toBeInTheDocument();
    });
  });

  it("sends non-admins home", async () => {
    me.data = { ...ADMIN, is_admin: false };
    render(<AdminPage />);
    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith("/");
    });
  });

  it("lets the admin switch a workspace to solo", async () => {
    render(<AdminPage />);
    const select = await screen.findByLabelText("Experience for Maya");
    fireEvent.change(select, { target: { value: "solo" } });
    await waitFor(() => {
      expect(setWorkspaceExperience).toHaveBeenCalledWith("ws_va", "solo");
    });
  });

  it("lets the admin set a trial source cap", async () => {
    render(<AdminPage />);
    const cap = await screen.findByLabelText("Source cap for Maya");
    fireEvent.change(cap, { target: { value: "5" } });
    await waitFor(() => {
      expect(cap).toHaveValue(5);
    });
    fireEvent.blur(cap);
    await waitFor(() => {
      expect(patchAdminWorkspace).toHaveBeenCalledWith("ws_va", {
        source_limit: 5,
        variants_per_source_limit: null,
      });
    });
  });

  it("shows week usage on the workspace row", async () => {
    render(<AdminPage />);
    expect(await screen.findByText("2 src · 16")).toBeInTheDocument();
    expect(screen.getByText("2 used")).toBeInTheDocument();
  });

  it("sends trial caps on a new-workspace invite", async () => {
    render(<AdminPage />);
    fireEvent.change(await screen.findByLabelText("Invite kind"), {
      target: { value: "new_workspace" },
    });
    fireEvent.change(screen.getByLabelText("Invite email"), {
      target: { value: "trial@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Trial source cap"), {
      target: { value: "4" },
    });
    fireEvent.change(screen.getByLabelText("Trial copies per source"), {
      target: { value: "10" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^invite$/i }));
    await waitFor(() => {
      expect(createInvite).toHaveBeenCalledWith("trial@example.com", "new_workspace", {
        source_limit: 4,
        variants_per_source_limit: 10,
      });
    });
  });
});
