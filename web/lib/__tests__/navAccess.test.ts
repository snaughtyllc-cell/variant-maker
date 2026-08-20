import { describe, it, expect } from "vitest";
import { showDiagnosticsNav, showTeamNav } from "@/lib/navAccess";

describe("showDiagnosticsNav", () => {
  it("hides for logged-in operators", () => {
    expect(showDiagnosticsNav({ auth_required: true, is_admin: false })).toBe(false);
  });

  it("shows for site admin", () => {
    expect(showDiagnosticsNav({ auth_required: true, is_admin: true })).toBe(true);
  });

  it("shows when login is off", () => {
    expect(showDiagnosticsNav({ auth_required: false, is_admin: false })).toBe(true);
  });
});

describe("showTeamNav", () => {
  it("shows for owners and site admin", () => {
    expect(showTeamNav({ role: "owner", is_admin: false })).toBe(true);
    expect(showTeamNav({ role: "member", is_admin: true })).toBe(true);
  });

  it("hides for members", () => {
    expect(showTeamNav({ role: "member", is_admin: false })).toBe(false);
  });
});
