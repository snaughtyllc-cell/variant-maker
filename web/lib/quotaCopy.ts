import type { Quota } from "./types";

export function quotaCaption(
  quota: Quota | null | undefined,
  kind: "fast" | "hq",
  need: number,
): string | null {
  if (!quota) return null;
  const limit = kind === "fast" ? quota.fast_limit : quota.hq_limit;
  if (limit == null) return null;
  const used = kind === "fast" ? quota.fast_used : quota.hq_used;
  const remaining = Math.max(0, limit - used);
  const windowDays = quota.window_days || 30;
  const label = kind === "fast" ? "Fast copies" : "HQ copies";
  return `${label}: ${used} / ${limit} in the last ${windowDays} days. This run needs ${need} (${remaining} left).`;
}

export function quotaBlocksRun(
  quota: Quota | null | undefined,
  kind: "fast" | "hq",
  need: number,
): boolean {
  if (!quota || need <= 0) return false;
  const limit = kind === "fast" ? quota.fast_limit : quota.hq_limit;
  if (limit == null) return false;
  const used = kind === "fast" ? quota.fast_used : quota.hq_used;
  return used + need > limit;
}
