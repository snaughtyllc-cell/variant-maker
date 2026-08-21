import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { AuthMe } from "@/lib/types";

const me: { data: AuthMe | undefined } = { data: undefined };

vi.mock("@/lib/useAuthMe", () => ({
  useAuthMe: () => me,
}));

import { DriveLoginNote } from "@/components/auth/DriveLoginNote";

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

beforeEach(() => {
  me.data = OWNER;
});

describe("DriveLoginNote", () => {
  it("tells operators to Connect Google and add a destination", () => {
    render(<DriveLoginNote />);
    expect(screen.getByText(/Connect Google once for this studio/i)).toBeInTheDocument();
    expect(screen.getByText(/destination folder/i)).toBeInTheDocument();
    expect(screen.getByText(/Send to Drive/i)).toBeInTheDocument();
  });

  it("hides when nobody is signed in", () => {
    me.data = undefined;
    const { container } = render(<DriveLoginNote />);
    expect(container).toBeEmptyDOMElement();
  });
});
