import { describe, it, expect } from "vitest";
import { canManageDriveOAuth, canManageInstagram, showDiagnosticsNav, showTeamNav, visiblePrimaryTabs } from "@/lib/navAccess";
import { PRIMARY_TABS } from "@/lib/studioDestinations";

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

describe("canManageDriveOAuth", () => {
  it("hides Connect Google from operators", () => {
    expect(canManageDriveOAuth({ auth_required: true, is_admin: false })).toBe(false);
  });

  it("lets the site admin connect", () => {
    expect(canManageDriveOAuth({ auth_required: true, is_admin: true })).toBe(true);
  });

  it("allows connect when login is off", () => {
    expect(canManageDriveOAuth({ auth_required: false, is_admin: false })).toBe(true);
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

describe("canManageInstagram", () => {
  it("lets any signed-in operator Connect another tester", () => {
    expect(canManageInstagram({ auth_required: true, email: "va@x.com" })).toBe(true);
  });

  it("hides Connect when login is required and nobody is signed in", () => {
    expect(canManageInstagram({ auth_required: true, email: null })).toBe(false);
  });

  it("allows Connect when login is off", () => {
    expect(canManageInstagram({ auth_required: false, email: null })).toBe(true);
  });
});

describe("visiblePrimaryTabs", () => {
  it("keeps every operator tab for agency, admin, and auth off", () => {
    const labels = PRIMARY_TABS.map((d) => d.label);
    expect(
      visiblePrimaryTabs({
        experience: "agency",
        is_admin: false,
        auth_required: true,
      }).map((d) => d.label),
    ).toEqual(labels);
    expect(
      visiblePrimaryTabs({
        experience: "solo",
        is_admin: true,
        auth_required: true,
      }).map((d) => d.label),
    ).toEqual(labels);
    expect(
      visiblePrimaryTabs({
        experience: "solo",
        is_admin: false,
        auth_required: false,
      }).map((d) => d.label),
    ).toEqual(labels);
  });

  it("hides Drops and Workflows for solo members", () => {
    expect(
      visiblePrimaryTabs({
        experience: "solo",
        is_admin: false,
        auth_required: true,
      }).map((d) => d.href),
    ).toEqual(["/", "/gallery", "/analytics", "/settings/drive"]);
  });
});
