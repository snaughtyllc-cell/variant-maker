import { isAgencyExperience } from "./experience";
import { PRIMARY_TABS, type StudioDestination } from "./studioDestinations";

const SOLO_PRIMARY_HREFS = new Set(["/", "/gallery", "/settings/drive"]);

/** Failed-encode leftovers. Operators never use Diagnostics — site admin only. */
export function showDiagnosticsNav(me: {
  auth_required?: boolean;
  is_admin?: boolean;
} | undefined): boolean {
  if (!me) return false;
  if (!me.auth_required) return true;
  return Boolean(me.is_admin);
}

export function showTeamNav(me: {
  role?: string | null;
  is_admin?: boolean;
} | undefined): boolean {
  return me?.role === "owner" || Boolean(me?.is_admin);
}

/** Phone + desktop primary row. Solo creators only see Studio, Gallery, Drive. */
export function visiblePrimaryTabs(me: {
  experience?: string | null;
  is_admin?: boolean;
  auth_required?: boolean;
} | undefined): readonly StudioDestination[] {
  if (isAgencyExperience(me)) return PRIMARY_TABS;
  return PRIMARY_TABS.filter((tab) => SOLO_PRIMARY_HREFS.has(tab.href));
}
