/** Copy + helpers for VA-pasted live post permalinks. Studio does not post. */

export function postLinkHint(): string {
  return (
    "After you post (phone, Repurpose, or a VA), paste the live Instagram / " +
    "TikTok / Shorts link. Studio does not post. Open it here to check views."
  );
}

export function postLinkLabel(): string {
  return "Live post link";
}

export function postLinkSaveLabel(): string {
  return "Save link";
}

export function postLinkOpenLabel(): string {
  return "Open post";
}

export function postLinkClearLabel(): string {
  return "Clear";
}

export function postedCountCopy(n: number): string | null {
  if (n <= 0) return null;
  return n === 1 ? "1 live post" : `${n} live posts`;
}

export function hostFromPostUrl(url: string): string {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    return host || url;
  } catch {
    return url;
  }
}
