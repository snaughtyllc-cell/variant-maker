import { describe, it, expect } from "vitest";
import { showDiagnosticsNav, showTeamNav, showWorkflowsNav } from "@/lib/navAccess";

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

describe("showWorkflowsNav", () => {
  it("hides on Creator", () => {
    expect(showWorkflowsNav({ auth_required: true, plan: "creator" })).toBe(false);
  });

  it("shows on Pro and when login is off", () => {
    expect(showWorkflowsNav({ auth_required: true, plan: "pro" })).toBe(true);
    expect(showWorkflowsNav({ auth_required: true, plan: "internal" })).toBe(true);
    expect(showWorkflowsNav({ auth_required: false })).toBe(true);
  });
});

describe("showTeamNav", () => {
  it("shows for owners and site admin on Pro+", () => {
    expect(showTeamNav({ role: "owner", is_admin: false, plan: "pro" })).toBe(true);
    expect(showTeamNav({ role: "member", is_admin: true, plan: "agency" })).toBe(true);
    expect(showTeamNav({ role: "owner", is_admin: false })).toBe(true);
  });

  it("hides for Creator even if they own the workspace", () => {
    expect(showTeamNav({ role: "owner", is_admin: false, plan: "creator" })).toBe(false);
    expect(showTeamNav({ role: "owner", is_admin: true, plan: "creator" })).toBe(false);
  });

  it("hides for members", () => {
    expect(showTeamNav({ role: "member", is_admin: false, plan: "pro" })).toBe(false);
  });
});
