export type WorkspaceExperience = "solo" | "agency";

export function normalizeExperience(raw: string | null | undefined): WorkspaceExperience {
  return raw === "solo" ? "solo" : "agency";
}

export function isAgencyExperience(me: {
  experience?: string | null;
  is_admin?: boolean;
  auth_required?: boolean;
} | undefined): boolean {
  if (!me) return true;
  if (me.auth_required === false) return true;
  if (me.is_admin) return true;
  return normalizeExperience(me.experience) === "agency";
}

export function experienceLabel(kind: WorkspaceExperience): string {
  return kind === "solo" ? "Solo creator" : "Agency";
}
