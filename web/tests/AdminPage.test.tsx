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
}));

import {
  createInvite,
  listAdminWorkspaces,
  listInvites,
  removeAdminUser,
  setAdminView,
  setWorkspaceExperience,
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
  vi.mocked(createInvite).mockReset();
  vi.mocked(setAdminView).mockResolvedValue(undefined);
  vi.mocked(removeAdminUser).mockResolvedValue(undefined);
  vi.mocked(setWorkspaceExperience).mockResolvedValue({
    ...workspaces[0],
    experience: "solo",
  });
});

describe("Admin page", () => {
  it("lists workspaces and Open switches view then goes home", async () => {
    render(<AdminPage />);
    expect((await screen.findAllByText("Maya")).length).toBeGreaterThan(0);
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

  it("lets the admin pick solo on a new-workspace invite before send", async () => {
    vi.mocked(createInvite).mockResolvedValue({
      id: "inv_new",
      email: "new@example.com",
      kind: "new_workspace",
      workspace_id: null,
      experience: "solo",
      workspace_name: "New studio",
      created_utc: "2026-08-27T00:00:00Z",
    });
    render(<AdminPage />);
    fireEvent.change(await screen.findByLabelText("Invite email"), {
      target: { value: "new@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Invite kind"), {
      target: { value: "new_workspace" },
    });
    expect(screen.getByLabelText("Workspace experience")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Workspace experience"), {
      target: { value: "solo" },
    });
    fireEvent.change(screen.getByLabelText("Studio name"), {
      target: { value: "New studio" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^invite$/i }));
    await waitFor(() => {
      expect(createInvite).toHaveBeenCalledWith("new@example.com", "new_workspace", {
        experience: "solo",
        workspaceName: "New studio",
      });
    });
    expect(await screen.findByText(/New workspace · Solo/)).toBeInTheDocument();
  });

  it("lets the admin pick an existing workspace on a join invite", async () => {
    vi.mocked(createInvite).mockResolvedValue({
      id: "inv_join",
      email: "helper@example.com",
      kind: "join",
      workspace_id: "ws_va",
      created_utc: "2026-08-27T00:00:00Z",
    });
    render(<AdminPage />);
    fireEvent.change(await screen.findByLabelText("Invite email"), {
      target: { value: "helper@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Join workspace"), {
      target: { value: "ws_va" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^invite$/i }));
    await waitFor(() => {
      expect(createInvite).toHaveBeenCalledWith("helper@example.com", "join", {
        workspaceId: "ws_va",
      });
    });
  });
});
