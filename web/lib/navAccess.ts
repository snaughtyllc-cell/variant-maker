import { isAgencyExperience } from "./experience";
import { PRIMARY_TABS, type StudioDestination } from "./studioDestinations";

const SOLO_PRIMARY_HREFS = new Set(["/", "/gallery", "/analytics", "/settings/drive"]);

/** Any signed-in workspace user can Connect another tester IG (not admin-only). */
export function canManageInstagram(me: {
  auth_required?: boolean;
  email?: string | null;
} | undefined): boolean {
  if (!me) return false;
  if (me.auth_required === false) return true;
  return Boolean(me.email);
}

/** Failed-encode leftovers. Operators never use Diagnostics — site admin only. */
export function showDiagnosticsNav(me: {
  auth_required?: boolean;
  is_admin?: boolean;
} | undefined): boolean {
  if (!me) return false;
  if (!me.auth_required) return true;
  return Boolean(me.is_admin);
}

/** OAuth Connect Google is site admin only. Operators share the studio mailbox. */
export function canManageDriveOAuth(me: {
  auth_required?: boolean;
  is_admin?: boolean;
} | undefined): boolean {
  if (!me) return false;
  if (me.auth_required === false) return true;
  return Boolean(me.is_admin);
}

export function showTeamNav(me: {
  role?: string | null;
  is_admin?: boolean;
} | undefined): boolean {
  return me?.role === "owner" || Boolean(me?.is_admin);
}

/** Phone + desktop primary row. Solo creators see Studio, Gallery, Analytics, Drive. */
export function visiblePrimaryTabs(me: {
  experience?: string | null;
  is_admin?: boolean;
  auth_required?: boolean;
} | undefined): readonly StudioDestination[] {
  if (isAgencyExperience(me)) return PRIMARY_TABS;
  return PRIMARY_TABS.filter((tab) => SOLO_PRIMARY_HREFS.has(tab.href));
}

/**
 * Role gate for the three "extra" destinations (Team / Admin / Diagnostics).
 * Shared by SideNav (desktop rail) and TopNav (mobile "More" flyout) so both
 * surfaces agree on exactly who sees what.
 */
export function extraTabVisible(
  href: string,
  me: { auth_required?: boolean; is_admin?: boolean; role?: string | null } | undefined,
): boolean {
  if (href === "/diagnostics") return showDiagnosticsNav(me);
  if (href === "/team") return showTeamNav(me);
  if (href === "/admin") return Boolean(me?.is_admin);
  return false;
}

/** Exact match for Studio ("/"), prefix match for every other destination. */
export function linkActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}
