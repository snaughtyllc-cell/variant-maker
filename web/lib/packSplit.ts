/** Pure pack-split preview math. Remainder on the first buckets. */

export const SPLIT_ROLES = [
  { key: "main", label: "Main" },
  { key: "trial", label: "Trial" },
  { key: "growth", label: "Growth" },
] as const;

export type SplitRole = (typeof SPLIT_ROLES)[number]["key"];

const ROLE_RE: Record<SplitRole, RegExp> = {
  main: /\bmain\b/i,
  trial: /\btrial\b/i,
  growth: /\bgrowth\b/i,
};

export function splitSizes(count: number, nDest: number): number[] {
  if (nDest <= 0) return [];
  const n = Math.max(0, Math.floor(count));
  const d = Math.floor(nDest);
  const base = Math.floor(n / d);
  const rem = n % d;
  return Array.from({ length: d }, (_, i) => base + (i < rem ? 1 : 0));
}

export function sliceRanges(sizes: number[]): { start: number; end: number; count: number }[] {
  let start = 1;
  return sizes.map((count) => {
    const c = Math.max(0, Math.floor(count));
    const end = c === 0 ? start - 1 : start + c - 1;
    const range = { start, end, count: c };
    start += c;
    return range;
  });
}

export function formatSlice(start: number, end: number, count: number): string {
  if (count <= 0) return "0 files";
  if (count === 1) return `1 file · ${start}`;
  return `${count} files · ${start}–${end}`;
}

export function assignedTotal(counts: number[]): number {
  return counts.reduce((sum, n) => sum + Math.max(0, Number(n) || 0), 0);
}

export function autoCountsForSlots(total: number, destIds: string[]): number[] {
  const n = destIds.filter(Boolean).length;
  const sizes = splitSizes(total, n);
  let k = 0;
  return destIds.map((id) => (id ? sizes[k++] ?? 0 : 0));
}

export function guessSlotDestinations(
  destinations: { id: string; name: string }[],
): string[] {
  const used = new Set<string>();
  return SPLIT_ROLES.map(({ key }) => {
    const hit = destinations.find((d) => !used.has(d.id) && ROLE_RE[key].test(d.name));
    if (!hit) return "";
    used.add(hit.id);
    return hit.id;
  });
}
