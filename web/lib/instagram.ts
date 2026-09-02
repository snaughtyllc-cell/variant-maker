/** Instagram Insights copy + view formatting. Unknown (unlinked) is not zero. */

export const AMPLIFY_MORE_N = 20;

export const INSTAGRAM_OAUTH_START = "/api/instagram/oauth/start";

export const INSTAGRAM_TESTER_HINT =
  "Testers only — Jeff adds your @handle on the Meta app. Accept the invite in " +
  "Instagram → Settings → Apps and websites → Tester invites, then tap Connect. " +
  "Each Connect adds another account (main / trial / growth). Studio stores the token; " +
  "you do not paste the long Meta generate-token string.";

export function formatViews(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  if (n < 1000) return String(Math.round(n));
  if (n < 1_000_000) {
    const k = n / 1000;
    const text = k >= 10 ? k.toFixed(0) : k.toFixed(1);
    return `${text.replace(/\.0$/, "")}k`;
  }
  return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
}

export function packViewsCopy(
  views: number | null | undefined,
  linked: number,
  copies: number,
): string | null {
  if (linked <= 0) return null;
  const label = views == null ? "views unknown" : `${formatViews(views)} views`;
  return `${label} · ${linked} of ${copies} linked`;
}

export function galleryViewsCopy(
  views: number | null | undefined,
  linked: number,
  accounts: number,
): string {
  if (accounts <= 0) {
    return "Connect Instagram testers on Analytics to pull Insights onto these packs.";
  }
  if (linked <= 0) {
    return `${accounts} account${accounts === 1 ? "" : "s"} connected. Sync to match Reels to copies.`;
  }
  const total = views == null ? "—" : formatViews(views);
  return `${total} views across ${linked} linked post${linked === 1 ? "" : "s"}`;
}

export function variantViewsCopy(views: number | null | undefined, linked: boolean): string | null {
  if (!linked) return null;
  if (views == null) return "linked";
  return formatViews(views);
}

export function insightSnapshotCopy(snapshot: {
  views?: number;
  reach?: number;
  likes?: number;
  comments?: number;
  shares?: number;
  saved?: number;
  fetched_at?: string;
} | null | undefined): string | null {
  if (!snapshot) return null;
  const parts: string[] = [];
  if (typeof snapshot.views === "number") parts.push(`${formatViews(snapshot.views)} views`);
  if (typeof snapshot.reach === "number") parts.push(`${formatViews(snapshot.reach)} reach`);
  if (typeof snapshot.likes === "number") parts.push(`${formatViews(snapshot.likes)} likes`);
  if (typeof snapshot.comments === "number") parts.push(`${formatViews(snapshot.comments)} comments`);
  if (typeof snapshot.shares === "number") parts.push(`${formatViews(snapshot.shares)} shares`);
  if (typeof snapshot.saved === "number") parts.push(`${formatViews(snapshot.saved)} saved`);
  if (parts.length === 0) return snapshot.fetched_at ? "Linked — Insights not in yet" : null;
  return parts.join(" · ");
}

export function igOauthErrorMessage(reason: string | null): string {
  switch (reason) {
    case "missing_code":
      return "Instagram came back without an auth code. Check the callback URL, then Connect again.";
    case "bad_state":
      return "Sign-in expired or was interrupted. Connect Instagram again.";
    case "exchange_failed":
      return "Instagram signed you in, but Studio could not store the token. Try Connect again.";
    case "access_denied":
      return "Instagram access was denied. Accept the tester invite, then Connect again.";
    default:
      return reason
        ? `Instagram sign-in failed (${reason}). Accept the tester invite, then Connect again.`
        : "Instagram sign-in failed. Accept the tester invite, then Connect again.";
  }
}

export function instagramTesterHint(): string {
  return INSTAGRAM_TESTER_HINT;
}

export function handleLabel(username: string): string {
  const trimmed = username.trim().replace(/^@/, "");
  return trimmed ? `@${trimmed}` : "Connected account";
}
