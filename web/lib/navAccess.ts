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
