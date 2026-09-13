import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { AuthMe, WorkspaceApiKeysPage } from "@/lib/types";

const replace = vi.fn();

const me: { data: AuthMe | undefined; isLoading: boolean } = {
  data: undefined,
  isLoading: false,
};

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/useAuthMe", () => ({
  useAuthMe: () => me,
}));

vi.mock("@/lib/api", () => ({
  getWorkspaceApiKeys: vi.fn(),
  createWorkspaceApiKey: vi.fn(),
  revokeWorkspaceApiKey: vi.fn(),
}));

import {
  createWorkspaceApiKey,
  getWorkspaceApiKeys,
  revokeWorkspaceApiKey,
} from "@/lib/api";
import IntegrationsPage from "@/app/settings/integrations/page";

const OWNER: AuthMe = {
  auth_required: true,
  email: "ops@example.com",
  name: "Ops",
  workspace_id: "ws_ops",
  workspace_name: "Ops studio",
  home_workspace_id: "ws_ops",
  viewing_other: false,
  role: "owner",
  is_admin: false,
  has_password: true,
};

const page: WorkspaceApiKeysPage = {
  workspace_id: "ws_ops",
  workspace_name: "Ops studio",
  destinations: [
    { id: "dst_in", name: "Inbox" },
    { id: "dst_out", name: "Out" },
  ],
  keys: [
    {
      key_id: "k1",
      label: "Old bot",
      prefix: "vf_aaa",
      scopes: ["jobs:read", "gallery:read"],
      created_utc: "2026-09-01T00:00:00Z",
      expires_utc: "2026-12-01T00:00:00Z",
      last_used_utc: null,
      revoked_utc: null,
    },
  ],
};

beforeEach(() => {
  replace.mockReset();
  me.data = OWNER;
  me.isLoading = false;
  vi.mocked(getWorkspaceApiKeys).mockResolvedValue(page);
  vi.mocked(createWorkspaceApiKey).mockResolvedValue({
    ...page.keys[0],
    key_id: "k2",
    label: "Agency bot",
    prefix: "vf_bbb",
    token: "vf_bbb_secret",
    scopes: ["jobs:create", "jobs:read", "gallery:read", "drive:export"],
  });
  vi.mocked(revokeWorkspaceApiKey).mockResolvedValue(undefined);
  Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

describe("IntegrationsPage", () => {
  it("creates a key and shows the token once", async () => {
    render(<IntegrationsPage />);
    await screen.findByText("Inbox");
    fireEvent.change(screen.getByLabelText("Key label"), { target: { value: "Agency bot" } });
    fireEvent.click(screen.getByRole("button", { name: "Create key" }));
    await screen.findByText("Copy this now. We cannot show it again.");
    expect(screen.getByText("vf_bbb_secret")).toBeTruthy();
    expect(createWorkspaceApiKey).toHaveBeenCalled();
  });

  it("redirects members home", async () => {
    me.data = { ...OWNER, role: "member" };
    render(<IntegrationsPage />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
  });

  it("revokes a live key", async () => {
    render(<IntegrationsPage />);
    await screen.findByText("Old bot");
    fireEvent.click(screen.getByRole("button", { name: "Revoke Old bot" }));
    await waitFor(() => expect(revokeWorkspaceApiKey).toHaveBeenCalledWith("k1"));
  });

  it("documents varimo-mcp on the agency machine", async () => {
    render(<IntegrationsPage />);
    await screen.findByText("On your machine");
    expect(screen.getAllByText(/varimo-mcp/).length).toBeGreaterThan(0);
    expect(screen.getByText(/VARIMO_BASE_URL/)).toBeTruthy();
    expect(screen.getByText(/paste-the-key-you-copied/)).toBeTruthy();
  });

  it("copies the selected Drive folder for the bot without showing the id", async () => {
    render(<IntegrationsPage />);
    await screen.findByText("Same folders as Drive");
    expect(screen.queryByText("dst_in")).toBeNull();
    expect(screen.queryByText("dst_out")).toBeNull();
    const picker = screen.getByLabelText("Drive folder");
    fireEvent.click(screen.getByRole("button", { name: "Copy selected Drive folder" }));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("dst_in");
    fireEvent.change(picker, { target: { value: "dst_out" } });
    fireEvent.click(screen.getByRole("button", { name: "Copy selected Drive folder" }));
    expect(navigator.clipboard.writeText).toHaveBeenLastCalledWith("dst_out");
    fireEvent.click(screen.getByRole("button", { name: "Copy on-your-machine setup" }));
    const snippet = vi.mocked(navigator.clipboard.writeText).mock.calls.at(-1)?.[0];
    expect(String(snippet)).toContain("VARIMO_BASE_URL=");
    expect(String(snippet)).toContain("varimo-mcp");
  });

  it("points to Drive when no folders are connected", async () => {
    vi.mocked(getWorkspaceApiKeys).mockResolvedValue({ ...page, destinations: [] });
    render(<IntegrationsPage />);
    await screen.findByText(/No Drive folders yet/);
    expect(screen.queryByLabelText("Drive folder")).toBeNull();
  });
});
