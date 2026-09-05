import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { AuthMe } from "@/lib/types";

const me: { data: AuthMe | undefined; mutate: ReturnType<typeof vi.fn> } = {
  data: undefined,
  mutate: vi.fn(),
};

vi.mock("@/lib/useAuthMe", () => ({
  useAuthMe: () => me,
}));

vi.mock("@/lib/api", () => ({
  setStudioPassword: vi.fn(),
}));

import { setStudioPassword } from "@/lib/api";
import { PasswordPanel } from "@/components/auth/PasswordPanel";

const LOGGED_IN: AuthMe = {
  auth_required: true,
  email: "jeff@example.com",
  name: "Jeff",
  workspace_id: "ws_1",
  workspace_name: "Jeff",
  home_workspace_id: "ws_1",
  viewing_other: false,
  role: "owner",
  is_admin: true,
  has_password: false,
};

beforeEach(() => {
  me.data = LOGGED_IN;
  me.mutate.mockReset();
  me.mutate.mockResolvedValue(undefined);
  vi.mocked(setStudioPassword).mockReset();
  vi.mocked(setStudioPassword).mockResolvedValue(undefined);
});

describe("PasswordPanel", () => {
  it("lets a Google-only user add a password", async () => {
    render(<PasswordPanel />);
    expect(screen.getByRole("button", { name: "Add password" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("New studio password"), {
      target: { value: "secret12" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add password" }));
    await waitFor(() => {
      expect(setStudioPassword).toHaveBeenCalledWith("secret12");
    });
    expect(await screen.findByText("Password saved.")).toBeInTheDocument();
  });
});
