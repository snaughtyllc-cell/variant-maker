import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { AuthMe } from "@/lib/types";

const me: { data: AuthMe | undefined } = { data: undefined };

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

vi.mock("@/lib/useAuthMe", () => ({
  useAuthMe: () => me,
}));

vi.mock("@/lib/api", () => ({
  logout: vi.fn(),
  setAdminView: vi.fn(),
}));

vi.mock("@/components/nav/StatusStrip", () => ({
  StatusStrip: () => <span>status</span>,
}));

import { TopNav } from "@/components/nav/TopNav";

const BASE: AuthMe = {
  auth_required: true,
  email: "ops@example.com",
  name: "Ops",
  workspace_id: "ws_ops",
  workspace_name: "Ops",
  home_workspace_id: "ws_ops",
  viewing_other: false,
  role: "owner",
  is_admin: false,
  has_password: true,
};

beforeEach(() => {
  me.data = BASE;
});

describe("TopNav", () => {
  it("shows Team for workspace owners", () => {
    render(<TopNav />);
    expect(screen.getAllByRole("link", { name: "Team" })[0]).toHaveAttribute("href", "/team");
    expect(screen.queryByRole("link", { name: "Admin" })).not.toBeInTheDocument();
  });

  it("hides Team for members", () => {
    me.data = { ...BASE, role: "member" };
    render(<TopNav />);
    expect(screen.queryByRole("link", { name: "Team" })).not.toBeInTheDocument();
  });

  it("shows Team and Admin for the site admin", () => {
    me.data = { ...BASE, email: "jeff@example.com", is_admin: true };
    render(<TopNav />);
    expect(screen.getAllByRole("link", { name: "Team" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Admin" })[0]).toHaveAttribute("href", "/admin");
  });

  it("hides Diagnostics for operators", () => {
    render(<TopNav />);
    expect(screen.queryByRole("link", { name: "Diagnostics" })).not.toBeInTheDocument();
  });

  it("shows Diagnostics for the site admin", () => {
    me.data = { ...BASE, email: "jeff@example.com", is_admin: true };
    render(<TopNav />);
    expect(screen.getAllByRole("link", { name: "Diagnostics" })[0]).toHaveAttribute(
      "href",
      "/diagnostics",
    );
  });

  it("keeps Diagnostics when login is off", () => {
    me.data = {
      ...BASE,
      auth_required: false,
      email: null,
      role: null,
      is_admin: false,
    };
    render(<TopNav />);
    expect(screen.getAllByRole("link", { name: "Diagnostics" }).length).toBeGreaterThan(0);
  });

  it("exposes all four primary destinations", () => {
    render(<TopNav />);
    expect(screen.getAllByRole("link", { name: "Studio" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Gallery" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Workflows" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Drive" }).length).toBeGreaterThan(0);
  });
});
