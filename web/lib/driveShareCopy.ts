/** Operator Drive setup: share the live connected mailbox, then paste the folder link. */

export const DEFAULT_DRIVE_SHARE_EMAIL = "snaughtyllc@gmail.com";

export function driveShareEmail(
  statusEmail?: string | null,
  connectedEmail?: string | null,
): string {
  const raw = (statusEmail || "").trim();
  if (raw) return raw;
  const connected = (connectedEmail || "").trim();
  return connected || DEFAULT_DRIVE_SHARE_EMAIL;
}

export const DRIVE_SHARE_HEADING = "Share this email";

export const DRIVE_SHARE_BODY =
  "Add this address as Editor on the Google Drive folder you want for import and export. Then paste the folder link below.";
