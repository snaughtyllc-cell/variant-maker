import type { DropFilter, DropPack } from "./types";

export const DROPS_EMPTY_COPY =
  "Nothing sent to Drive yet — Generate, then Send to Drive.";

const DAY_MS = 24 * 60 * 60 * 1000;

export function sentWithinDays(createdUtc: string, days: number, now = Date.now()): boolean {
  const t = Date.parse(createdUtc);
  if (Number.isNaN(t)) return false;
  return now - t <= days * DAY_MS;
}

export function filterDropPacks(
  packs: DropPack[],
  mode: DropFilter,
  now = Date.now(),
): DropPack[] {
  if (mode === "all") return packs;
  if (mode === "week") return packs.filter((p) => sentWithinDays(p.created_utc, 7, now));
  if (mode === "misses") return packs.filter((p) => p.outcome === "miss");
  return packs.filter(
    (p) => p.outcome === "miss" && sentWithinDays(p.created_utc, 7, now),
  );
}

export function dropStats(packs: DropPack[]): {
  sent: number;
  misses: number;
  winRate: number | null;
} {
  const sent = packs.reduce((n, p) => n + p.count, 0);
  const misses = packs.reduce(
    (n, p) => n + p.files.filter((f) => f.outcome === "miss").length,
    0,
  );
  return { sent, misses, winRate: sent === 0 ? null : (sent - misses) / sent };
}

export function formatSendDay(createdUtc: string): string {
  const t = Date.parse(createdUtc);
  if (Number.isNaN(t)) return createdUtc;
  return new Date(t).toISOString().slice(0, 10);
}

export function parseDropFilter(raw: string | null): DropFilter {
  if (raw === "week" || raw === "misses" || raw === "flagged_week") return raw;
  return "all";
}
