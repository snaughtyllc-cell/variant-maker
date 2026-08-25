/** Failed-encode leftovers. Operators never use Diagnostics — site admin only. */
export function showDiagnosticsNav(me: {
  auth_required?: boolean;
  is_admin?: boolean;
} | undefined): boolean {
  if (!me) return false;
  if (!me.auth_required) return true;
  return Boolean(me.is_admin);
}

export function showWorkflowsNav(me: {
  auth_required?: boolean;
  plan?: string | null;
} | undefined): boolean {
  if (!me) return false;
  if (!me.auth_required) return true;
  const plan = (me.plan || "internal").toLowerCase();
  return plan !== "creator";
}

export function showTeamNav(me: {
  role?: string | null;
  is_admin?: boolean;
  plan?: string | null;
} | undefined): boolean {
  const plan = (me?.plan || "internal").toLowerCase();
  if (plan === "creator") return false;
  return me?.role === "owner" || Boolean(me?.is_admin);
}
