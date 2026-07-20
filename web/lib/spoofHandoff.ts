/** Queue a Create handoff MP4 for Spoof Studio (`/`). */

export const SPOOF_HANDOFF_KEY = "vm.spoof.pending";

export interface SpoofHandoffPayload {
  url: string;
  filename: string;
}

export function queueSpoofHandoff(payload: SpoofHandoffPayload): void {
  sessionStorage.setItem(SPOOF_HANDOFF_KEY, JSON.stringify(payload));
}

export function consumeSpoofHandoff(): SpoofHandoffPayload | null {
  const raw = sessionStorage.getItem(SPOOF_HANDOFF_KEY);
  if (!raw) return null;
  sessionStorage.removeItem(SPOOF_HANDOFF_KEY);
  try {
    const parsed = JSON.parse(raw) as SpoofHandoffPayload;
    if (!parsed?.url || !parsed?.filename) return null;
    return parsed;
  } catch {
    return null;
  }
}

/** Fetch handoff MP4 bytes and build a File ready for POST /api/jobs. */
export async function fetchHandoffFile(
  url: string,
  filename: string,
): Promise<File> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch handoff (${res.status})`);
  const blob = await res.blob();
  const name = filename.endsWith(".mp4") ? filename : `${filename}.mp4`;
  return new File([blob], name, { type: blob.type || "video/mp4" });
}

/**
 * Queue Create handoff → navigate to Spoof Studio with the file ready.
 * Caller should `router.push("/")` after this returns.
 */
export async function spoofCreateHandoff(opts: {
  handoffUrl: string;
  handoffFilename: string;
}): Promise<void> {
  // Validate fetchability before navigating so Studio can load immediately.
  await fetchHandoffFile(opts.handoffUrl, opts.handoffFilename);
  queueSpoofHandoff({
    url: opts.handoffUrl,
    filename: opts.handoffFilename,
  });
}
